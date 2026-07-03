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

    @patch.dict(os.environ, {'FROM_EMAIL': 'custom@example.com'})
    @patch('services.mail_service.boto3.client')
    def test_send_email_uses_env_var(self, mock_boto3_client):
        """Test that FROM_EMAIL environment variable is used when set"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send without specifying from_email (should use env var)
        send_email(
            to_addresses=['recipient@example.com'],
            subject='Test',
            body_text='Test body'
        )

        # Verify env var sender is used
        call_args = mock_ses.send_raw_email.call_args[1]
        assert call_args['Source'] == 'custom@example.com'

    @patch.dict(os.environ, {}, clear=True)
    @patch('services.mail_service.boto3.client')
    def test_send_email_fallback_when_env_var_not_set(self, mock_boto3_client):
        """Test that fallback to noreply@goinvoi.com works when FROM_EMAIL not set"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send without specifying from_email (should use fallback)
        send_email(
            to_addresses=['recipient@example.com'],
            subject='Test',
            body_text='Test body'
        )

        # Verify fallback sender is used
        call_args = mock_ses.send_raw_email.call_args[1]
        assert call_args['Source'] == 'noreply@goinvoi.com'

    @patch.dict(os.environ, {'FROM_EMAIL': 'env@example.com'})
    @patch('services.mail_service.boto3.client')
    def test_send_email_explicit_overrides_env_var(self, mock_boto3_client):
        """Test that explicit from_email parameter overrides env var"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send with explicit from_email (should override env var)
        send_email(
            to_addresses=['recipient@example.com'],
            subject='Test',
            body_text='Test body',
            from_email='explicit@example.com'
        )

        # Verify explicit sender is used
        call_args = mock_ses.send_raw_email.call_args[1]
        assert call_args['Source'] == 'explicit@example.com'


class TestSendWeeklyEmail:
    """Tests for send_weekly_email() function"""

    @patch.dict(os.environ, {'FROM_EMAIL': 'custom@example.com'})
    @patch('services.mail_service.boto3.client')
    def test_send_weekly_email_uses_env_var(self, mock_boto3_client):
        """Test that send_weekly_email uses FROM_EMAIL environment variable when set"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send weekly email without specifying from_email
        send_weekly_email(
            to_addresses=['client@example.com'],
            user_name='Test User',
            week_start='Jan 1',
            week_end='Jan 7, 2026',
            total_hours=40,
            total_pay=1000.00,
            pdf_data=b'fake pdf content',
            pdf_filename='invoice.pdf'
        )

        # Verify env var is used in the from address
        call_args = mock_ses.send_raw_email.call_args[1]
        assert 'custom@example.com' in call_args['Source']
        assert 'Test User' in call_args['Source']

    @patch.dict(os.environ, {}, clear=True)
    @patch('services.mail_service.boto3.client')
    def test_send_weekly_email_fallback_when_env_var_not_set(self, mock_boto3_client):
        """Test that send_weekly_email falls back to noreply@goinvoi.com when FROM_EMAIL not set"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send weekly email without specifying from_email
        send_weekly_email(
            to_addresses=['client@example.com'],
            user_name='Test User',
            week_start='Jan 1',
            week_end='Jan 7, 2026',
            total_hours=40,
            total_pay=1000.00,
            pdf_data=b'fake pdf content',
            pdf_filename='invoice.pdf'
        )

        # Verify fallback is used
        call_args = mock_ses.send_raw_email.call_args[1]
        assert 'noreply@goinvoi.com' in call_args['Source']
        assert 'Test User' in call_args['Source']

    @patch.dict(os.environ, {'FROM_EMAIL': 'env@example.com'})
    @patch('services.mail_service.boto3.client')
    def test_send_weekly_email_explicit_overrides_env_var(self, mock_boto3_client):
        """Test that explicit from_email parameter overrides env var in send_weekly_email"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send weekly email with explicit from_email
        send_weekly_email(
            to_addresses=['client@example.com'],
            user_name='Test User',
            week_start='Jan 1',
            week_end='Jan 7, 2026',
            total_hours=40,
            total_pay=1000.00,
            pdf_data=b'fake pdf content',
            pdf_filename='invoice.pdf',
            from_email='explicit@example.com'
        )

        # Verify explicit sender is used
        call_args = mock_ses.send_raw_email.call_args[1]
        assert 'explicit@example.com' in call_args['Source']
        assert 'Test User' in call_args['Source']


class TestSendMonthlyEmail:
    """Tests for send_monthly_email() function"""

    @patch.dict(os.environ, {'FROM_EMAIL': 'custom@example.com'})
    @patch('services.mail_service.boto3.client')
    def test_send_monthly_email_uses_env_var(self, mock_boto3_client):
        """Test that send_monthly_email uses FROM_EMAIL environment variable when set"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send monthly email without specifying from_email
        send_monthly_email(
            to_addresses=['client@example.com'],
            user_name='Test User',
            month_label='March 2026',
            total_hours=160,
            total_pay=4000.00,
            pdf_data=b'fake pdf content',
            pdf_filename='report.pdf'
        )

        # Verify env var is used in the from address
        call_args = mock_ses.send_raw_email.call_args[1]
        assert 'custom@example.com' in call_args['Source']
        assert 'Test User' in call_args['Source']

    @patch.dict(os.environ, {}, clear=True)
    @patch('services.mail_service.boto3.client')
    def test_send_monthly_email_fallback_when_env_var_not_set(self, mock_boto3_client):
        """Test that send_monthly_email falls back to noreply@goinvoi.com when FROM_EMAIL not set"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send monthly email without specifying from_email
        send_monthly_email(
            to_addresses=['client@example.com'],
            user_name='Test User',
            month_label='March 2026',
            total_hours=160,
            total_pay=4000.00,
            pdf_data=b'fake pdf content',
            pdf_filename='report.pdf'
        )

        # Verify fallback is used
        call_args = mock_ses.send_raw_email.call_args[1]
        assert 'noreply@goinvoi.com' in call_args['Source']
        assert 'Test User' in call_args['Source']

    @patch.dict(os.environ, {'FROM_EMAIL': 'env@example.com'})
    @patch('services.mail_service.boto3.client')
    def test_send_monthly_email_explicit_overrides_env_var(self, mock_boto3_client):
        """Test that explicit from_email parameter overrides env var in send_monthly_email"""
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_boto3_client.return_value = mock_ses

        # Send monthly email with explicit from_email
        send_monthly_email(
            to_addresses=['client@example.com'],
            user_name='Test User',
            month_label='March 2026',
            total_hours=160,
            total_pay=4000.00,
            pdf_data=b'fake pdf content',
            pdf_filename='report.pdf',
            from_email='explicit@example.com'
        )

        # Verify explicit sender is used
        call_args = mock_ses.send_raw_email.call_args[1]
        assert 'explicit@example.com' in call_args['Source']
        assert 'Test User' in call_args['Source']


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
