"""Tests for services.error_reporter — per-request SNS reporting of Lambda 500s."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services import error_reporter
from botocore.exceptions import ClientError


@pytest.fixture(autouse=True)
def reset_sns_client():
    """Force a fresh boto3 client between tests so each patch is isolated."""
    error_reporter._sns_client = None
    yield
    error_reporter._sns_client = None


class TestReportException:
    """Tests for report_exception() helper."""

    def test_returns_false_when_topic_not_configured(self):
        """Without ALARM_TOPIC_ARN set, reporter is a no-op that returns False."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('ALARM_TOPIC_ARN', None)
            with patch('services.error_reporter.boto3') as mock_boto3:
                result = error_reporter.report_exception(
                    handler_name='submit_weekly',
                    exc=ValueError('boom'),
                )
                assert result is False
                mock_boto3.client.assert_not_called()

    def test_publishes_to_sns_when_topic_configured(self):
        """With ALARM_TOPIC_ARN set, reporter publishes a serialized message to SNS."""
        mock_sns = MagicMock()
        mock_sns.publish.return_value = {'MessageId': 'abc-123'}

        event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/api/submit/weekly'},
                'requestId': 'req-456',
            }
        }

        with patch.dict(os.environ, {'ALARM_TOPIC_ARN': 'arn:aws:sns:us-east-1:123:InvoiAlarmTopic'}):
            with patch('services.error_reporter.boto3') as mock_boto3:
                mock_boto3.client.return_value = mock_sns
                result = error_reporter.report_exception(
                    handler_name='submit_weekly',
                    exc=TypeError("can't multiply sequence by non-int of type 'float'"),
                    event=event,
                    user_id='user-123',
                )

        assert result is True
        mock_sns.publish.assert_called_once()
        call_kwargs = mock_sns.publish.call_args.kwargs
        assert call_kwargs['TopicArn'] == 'arn:aws:sns:us-east-1:123:InvoiAlarmTopic'
        assert 'submit_weekly' in call_kwargs['Subject']
        assert 'TypeError' in call_kwargs['Subject']

        # Message body should be JSON with the key context fields
        import json
        payload = json.loads(call_kwargs['Message'])
        assert payload['handler'] == 'submit_weekly'
        assert payload['exception_type'] == 'TypeError'
        assert "can't multiply sequence" in payload['exception_message']
        assert payload['user_id'] == 'user-123'
        assert payload['method'] == 'POST'
        assert payload['path'] == '/api/submit/weekly'
        assert 'timestamp' in payload

    def test_swallows_sns_client_error(self):
        """If SNS publish fails, reporter returns False and never raises."""
        mock_sns = MagicMock()
        mock_sns.publish.side_effect = ClientError(
            error_response={'Error': {'Code': 'NotFound', 'Message': 'topic missing'}},
            operation_name='Publish',
        )

        with patch.dict(os.environ, {'ALARM_TOPIC_ARN': 'arn:aws:sns:us-east-1:123:Missing'}):
            with patch('services.error_reporter.boto3') as mock_boto3:
                mock_boto3.client.return_value = mock_sns
                result = error_reporter.report_exception(
                    handler_name='config',
                    exc=RuntimeError('original bug'),
                )

        assert result is False

    def test_swallows_unexpected_reporter_failure(self):
        """Even truly unexpected failures (e.g. JSON serialization) must not raise."""
        with patch.dict(os.environ, {'ALARM_TOPIC_ARN': 'arn:aws:sns:us-east-1:123:Topic'}):
            with patch('services.error_reporter.boto3') as mock_boto3:
                # Make boto3.client() itself raise something weird
                mock_boto3.client.side_effect = RuntimeError('boto3 broken')
                result = error_reporter.report_exception(
                    handler_name='submit_monthly',
                    exc=Exception('original'),
                )
        assert result is False

    def test_includes_extra_context_when_provided(self):
        """Caller can pass an `extra` dict that gets embedded in the SNS message."""
        mock_sns = MagicMock()
        with patch.dict(os.environ, {'ALARM_TOPIC_ARN': 'arn:aws:sns:us-east-1:123:Topic'}):
            with patch('services.error_reporter.boto3') as mock_boto3:
                mock_boto3.client.return_value = mock_sns
                error_reporter.report_exception(
                    handler_name='submit_weekly',
                    exc=ValueError('boom'),
                    extra={'invoiceNumber': 'INV-20260324', 'rate_type': 'str'},
                )

        import json
        payload = json.loads(mock_sns.publish.call_args.kwargs['Message'])
        assert payload['extra'] == {'invoiceNumber': 'INV-20260324', 'rate_type': 'str'}

    def test_handles_missing_event_fields_gracefully(self):
        """A minimal event dict with no requestContext/http should still publish."""
        mock_sns = MagicMock()
        with patch.dict(os.environ, {'ALARM_TOPIC_ARN': 'arn:aws:sns:us-east-1:123:Topic'}):
            with patch('services.error_reporter.boto3') as mock_boto3:
                mock_boto3.client.return_value = mock_sns
                result = error_reporter.report_exception(
                    handler_name='config',
                    exc=ValueError('bad input'),
                    event={},  # no requestContext
                )

        assert result is True
        import json
        payload = json.loads(mock_sns.publish.call_args.kwargs['Message'])
        assert payload['method'] is None
        assert payload['path'] is None
