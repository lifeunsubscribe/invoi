"""
Tests for mail_service.py

Tests email sending logic and email body template generation.
SES API calls are mocked to avoid actual email sending during tests.
"""

import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.mail_service import (
    send_email,
    send_weekly_email,
    send_monthly_email,
    create_weekly_email_body,
    create_weekly_with_logs_email_body,
    create_monthly_email_body
)


class TestSendEmail:
    """Tests for send_email() function"""

    @patch('services.mail_service.boto3.client')
    def test_send_email_basic(self, mock_boto3_client):
        """Test basic email sending without attachments"""
        # Mock SES client response
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id-123'}
        mock_boto3_client.return_value = mock_ses

        # Send email
        response = send_email(
            to_addresses=['recipient@example.com'],
            subject='Test Subject',
            body_text='Test email body',
            from_email='noreply@goinvoi.com'
        )

        # Verify SES was called
        assert mock_ses.send_raw_email.called
        call_args = mock_ses.send_raw_email.call_args[1]
        assert call_args['Source'] == 'noreply@goinvoi.com'
        assert call_args['Destinations'] == ['recipient@example.com']
        assert 'RawMessage' in call_args
        assert response['MessageId'] == 'test-message-id-123'

    @patch('services.mail_service.boto3.client')
    def test_send_email_with_attachment(self, mock_boto3_client):
        """Test email sending with PDF attachment"""
        # Mock SES client
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id-456'}
        mock_boto3_client.return_value = mock_ses

        # Create fake PDF data
        attachments = [
            {
                'filename': 'invoice.pdf',
                'data': b'%PDF-1.4 fake pdf content'
            }
        ]

        # Send email with attachment
        response = send_email(
            to_addresses=['recipient@example.com'],
            subject='Invoice Attached',
            body_text='Please find your invoice attached.',
            attachments=attachments,
            from_email='noreply@goinvoi.com'
        )

        # Verify attachment was included
        assert mock_ses.send_raw_email.called
        call_args = mock_ses.send_raw_email.call_args[1]
        raw_message = call_args['RawMessage']['Data']
        assert 'invoice.pdf' in raw_message
        assert response['MessageId'] == 'test-message-id-456'

    @patch('services.mail_service.boto3.client')
    def test_send_email_multiple_recipients(self, mock_boto3_client):
        """Test sending to multiple recipients"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id-789'}
        mock_boto3_client.return_value = mock_ses

        # Send to multiple recipients
        response = send_email(
            to_addresses=['recipient1@example.com', 'recipient2@example.com'],
            subject='Test',
            body_text='Test body'
        )

        # Verify both recipients
        call_args = mock_ses.send_raw_email.call_args[1]
        assert call_args['Destinations'] == ['recipient1@example.com', 'recipient2@example.com']

    @patch('services.mail_service.boto3.client')
    def test_send_email_string_recipient(self, mock_boto3_client):
        """Test sending with single string recipient (should convert to list)"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send with string instead of list
        send_email(
            to_addresses='recipient@example.com',
            subject='Test',
            body_text='Test body'
        )

        # Verify converted to list
        call_args = mock_ses.send_raw_email.call_args[1]
        assert call_args['Destinations'] == ['recipient@example.com']

    def test_send_email_empty_recipients(self):
        """Test that empty recipient list raises ValueError"""
        with pytest.raises(ValueError, match="to_addresses cannot be empty"):
            send_email(
                to_addresses=[],
                subject='Test',
                body_text='Test body'
            )

    @patch('services.mail_service.boto3.client')
    def test_send_email_ses_error(self, mock_boto3_client):
        """Test handling of SES ClientError"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.side_effect = ClientError(
            {'Error': {'Code': 'MessageRejected', 'Message': 'Email address not verified'}},
            'SendRawEmail'
        )
        mock_boto3_client.return_value = mock_ses

        # Verify error is raised
        with pytest.raises(ClientError):
            send_email(
                to_addresses=['unverified@example.com'],
                subject='Test',
                body_text='Test body'
            )

    @patch('services.mail_service.boto3.client')
    def test_send_email_throttling_error(self, mock_boto3_client):
        """Test handling of SES throttling/rate limit error"""
        mock_ses = MagicMock()
        # Simulate AWS throttling error (common in production when sending too many emails)
        mock_ses.send_raw_email.side_effect = ClientError(
            {'Error': {'Code': 'Throttling', 'Message': 'Maximum sending rate exceeded'}},
            'SendRawEmail'
        )
        mock_boto3_client.return_value = mock_ses

        # Verify error is raised and propagated
        with pytest.raises(ClientError) as exc_info:
            send_email(
                to_addresses=['recipient@example.com'],
                subject='Test',
                body_text='Test body'
            )

        assert exc_info.value.response['Error']['Code'] == 'Throttling'

    @patch('services.mail_service.boto3.client')
    def test_send_email_service_unavailable(self, mock_boto3_client):
        """Test handling of SES service unavailable error"""
        mock_ses = MagicMock()
        # Simulate AWS service outage/unavailability
        mock_ses.send_raw_email.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service is temporarily unavailable'}},
            'SendRawEmail'
        )
        mock_boto3_client.return_value = mock_ses

        with pytest.raises(ClientError) as exc_info:
            send_email(
                to_addresses=['recipient@example.com'],
                subject='Test',
                body_text='Test body'
            )

        assert exc_info.value.response['Error']['Code'] == 'ServiceUnavailable'

    @patch('services.mail_service.boto3.client')
    def test_send_email_account_sending_paused(self, mock_boto3_client):
        """Test handling of SES account sending paused error"""
        mock_ses = MagicMock()
        # Simulate account sending being paused (e.g., due to bounce rate)
        mock_ses.send_raw_email.side_effect = ClientError(
            {'Error': {'Code': 'AccountSendingPausedException', 'Message': 'Account sending has been paused'}},
            'SendRawEmail'
        )
        mock_boto3_client.return_value = mock_ses

        with pytest.raises(ClientError) as exc_info:
            send_email(
                to_addresses=['recipient@example.com'],
                subject='Test',
                body_text='Test body'
            )

        assert exc_info.value.response['Error']['Code'] == 'AccountSendingPausedException'

    @patch('services.mail_service.boto3.client')
    def test_send_email_configuration_set_error(self, mock_boto3_client):
        """Test handling of SES configuration set error"""
        mock_ses = MagicMock()
        # Simulate configuration set not found error
        mock_ses.send_raw_email.side_effect = ClientError(
            {'Error': {'Code': 'ConfigurationSetDoesNotExist', 'Message': 'Configuration set does not exist'}},
            'SendRawEmail'
        )
        mock_boto3_client.return_value = mock_ses

        with pytest.raises(ClientError) as exc_info:
            send_email(
                to_addresses=['recipient@example.com'],
                subject='Test',
                body_text='Test body'
            )

        assert exc_info.value.response['Error']['Code'] == 'ConfigurationSetDoesNotExist'

    @patch('services.mail_service.boto3.client')
    def test_send_email_default_sender(self, mock_boto3_client):
        """Test default from_email is noreply@goinvoi.com"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send without specifying from_email
        send_email(
            to_addresses=['recipient@example.com'],
            subject='Test',
            body_text='Test body'
        )

        # Verify default sender
        call_args = mock_ses.send_raw_email.call_args[1]
        assert call_args['Source'] == 'noreply@goinvoi.com'


class TestEmailBodyTemplates:
    """Tests for email body template generation functions"""

    def test_create_weekly_email_body(self):
        """Test weekly invoice email body"""
        body = create_weekly_email_body(
            name="Lisa Wadley",
            week_start="March 24",
            week_end="March 30, 2026",
            total_hours=40,
            total_pay=1120.00
        )

        assert "Lisa Wadley" in body
        assert "March 24" in body
        assert "March 30, 2026" in body
        assert "40" in body
        assert "$1120.00" in body
        assert "invoice" in body.lower()

    def test_create_weekly_with_logs_email_body(self):
        """Test weekly invoice + service log email body"""
        body = create_weekly_with_logs_email_body(
            name="Lisa Wadley",
            week_start="March 24",
            week_end="March 30, 2026",
            total_hours=40,
            total_pay=1120.00
        )

        assert "Lisa Wadley" in body
        assert "service log" in body.lower()
        assert "40" in body
        assert "$1120.00" in body

    def test_create_monthly_email_body(self):
        """Test monthly report email body"""
        body = create_monthly_email_body(
            name="Lisa Wadley",
            month_label="March 2026",
            total_hours=160,
            total_pay=4480.00
        )

        assert "Lisa Wadley" in body
        assert "March 2026" in body
        assert "160" in body
        assert "$4480.00" in body
        assert "monthly" in body.lower()

    def test_email_body_formatting(self):
        """Test that email bodies are properly formatted"""
        body = create_weekly_email_body(
            name="Test User",
            week_start="Jan 1",
            week_end="Jan 7, 2026",
            total_hours=35.5,
            total_pay=994.00
        )

        # Check decimal formatting
        assert "$994.00" in body
        # Check that total hours is included
        assert "35.5" in body

    def test_monthly_email_mentions_weekly_invoices(self):
        """Test that monthly email mentions individual weekly invoices"""
        body = create_monthly_email_body(
            name="Test User",
            month_label="March 2026",
            total_hours=160,
            total_pay=4480.00
        )

        assert "weekly invoices" in body.lower()


class TestSendWeeklyEmail:
    """Tests for send_weekly_email() wrapper function"""

    @patch('services.mail_service.boto3.client')
    def test_send_weekly_email_success(self, mock_boto3_client):
        """Test successful weekly invoice email send"""
        # Mock SES client
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'weekly-msg-id'}
        mock_boto3_client.return_value = mock_ses

        # Send weekly invoice email
        response = send_weekly_email(
            to_addresses=['client@example.com'],
            user_name='Lisa Wadley',
            week_start='March 24',
            week_end='March 30, 2026',
            total_hours=40,
            total_pay=1120.00,
            pdf_data=b'fake-invoice-pdf',
            pdf_filename='INV-001.pdf'
        )

        # Verify SES was called
        assert mock_ses.send_raw_email.called
        assert response['MessageId'] == 'weekly-msg-id'

        # Verify call arguments include display name
        call_args = mock_ses.send_raw_email.call_args[1]
        assert 'Lisa Wadley' in call_args['Source']

    @patch('services.mail_service.boto3.client')
    def test_send_weekly_email_with_logs(self, mock_boto3_client):
        """Test weekly invoice email with service logs attached"""
        # Mock SES client
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'weekly-with-logs-msg-id'}
        mock_boto3_client.return_value = mock_ses

        # Send weekly invoice email with logs
        response = send_weekly_email(
            to_addresses=['client@example.com'],
            user_name='Lisa Wadley',
            week_start='March 24',
            week_end='March 30, 2026',
            total_hours=40,
            total_pay=1120.00,
            pdf_data=b'fake-invoice-pdf',
            pdf_filename='INV-001.pdf',
            include_logs=True,
            log_pdf_data=b'fake-log-pdf',
            log_pdf_filename='LOG-001.pdf'
        )

        # Verify SES was called
        assert mock_ses.send_raw_email.called
        assert response['MessageId'] == 'weekly-with-logs-msg-id'

    def test_send_weekly_email_logs_without_data(self):
        """Test that include_logs=True without log data raises ValueError"""
        with pytest.raises(ValueError):
            send_weekly_email(
                to_addresses=['client@example.com'],
                user_name='Lisa Wadley',
                week_start='March 24',
                week_end='March 30, 2026',
                total_hours=40,
                total_pay=1120.00,
                pdf_data=b'fake-invoice-pdf',
                pdf_filename='INV-001.pdf',
                include_logs=True  # Missing log_pdf_data and log_pdf_filename
            )

    def test_send_weekly_email_empty_recipients(self):
        """Test that empty to_addresses raises ValueError"""
        with pytest.raises(ValueError):
            send_weekly_email(
                to_addresses=[],
                user_name='Lisa Wadley',
                week_start='March 24',
                week_end='March 30, 2026',
                total_hours=40,
                total_pay=1120.00,
                pdf_data=b'fake-invoice-pdf',
                pdf_filename='INV-001.pdf'
            )

    def test_send_weekly_email_missing_pdf_data(self):
        """Test that missing pdf_data raises ValueError"""
        with pytest.raises(ValueError):
            send_weekly_email(
                to_addresses=['client@example.com'],
                user_name='Lisa Wadley',
                week_start='March 24',
                week_end='March 30, 2026',
                total_hours=40,
                total_pay=1120.00,
                pdf_data=None,
                pdf_filename='INV-001.pdf'
            )


class TestSendMonthlyEmail:
    """Tests for send_monthly_email() wrapper function"""

    @patch('services.mail_service.boto3.client')
    def test_send_monthly_email_success(self, mock_boto3_client):
        """Test successful monthly report email send"""
        # Mock SES client
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'monthly-msg-id'}
        mock_boto3_client.return_value = mock_ses

        # Send monthly report email
        response = send_monthly_email(
            to_addresses=['client@example.com'],
            user_name='Lisa Wadley',
            month_label='March 2026',
            total_hours=160,
            total_pay=4480.00,
            pdf_data=b'fake-report-pdf',
            pdf_filename='RPT-2026-03.pdf'
        )

        # Verify SES was called
        assert mock_ses.send_raw_email.called
        assert response['MessageId'] == 'monthly-msg-id'

        # Verify call arguments include display name
        call_args = mock_ses.send_raw_email.call_args[1]
        assert 'Lisa Wadley' in call_args['Source']

    def test_send_monthly_email_empty_recipients(self):
        """Test that empty to_addresses raises ValueError"""
        with pytest.raises(ValueError):
            send_monthly_email(
                to_addresses=[],
                user_name='Lisa Wadley',
                month_label='March 2026',
                total_hours=160,
                total_pay=4480.00,
                pdf_data=b'fake-report-pdf',
                pdf_filename='RPT-2026-03.pdf'
            )

    def test_send_monthly_email_missing_pdf_data(self):
        """Test that missing pdf_data raises ValueError"""
        with pytest.raises(ValueError):
            send_monthly_email(
                to_addresses=['client@example.com'],
                user_name='Lisa Wadley',
                month_label='March 2026',
                total_hours=160,
                total_pay=4480.00,
                pdf_data=None,
                pdf_filename='RPT-2026-03.pdf'
            )
