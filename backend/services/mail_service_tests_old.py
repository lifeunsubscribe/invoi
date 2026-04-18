"""
Unit tests for mail_service.py

Tests email template generation and SES wrapper functions.
"""

import unittest
from unittest.mock import patch, MagicMock
from mail_service import (
    send_email,
    send_weekly_email,
    send_monthly_email,
    create_weekly_email_body,
    create_weekly_with_logs_email_body,
    create_monthly_email_body
)


class TestEmailTemplates(unittest.TestCase):
    """Test email body template generation functions."""

    def test_create_weekly_email_body(self):
        """Test weekly invoice email template."""
        body = create_weekly_email_body(
            name="Lisa Wadley",
            week_start="March 24",
            week_end="March 30, 2026",
            total_hours=40,
            total_pay=1120.00
        )

        self.assertIn("March 24", body)
        self.assertIn("March 30, 2026", body)
        self.assertIn("40", body)
        self.assertIn("$1120.00", body)
        self.assertIn("Lisa Wadley", body)

    def test_create_weekly_with_logs_email_body(self):
        """Test weekly invoice + logs email template."""
        body = create_weekly_with_logs_email_body(
            name="Lisa Wadley",
            week_start="March 24",
            week_end="March 30, 2026",
            total_hours=40,
            total_pay=1120.00
        )

        self.assertIn("service log", body)
        self.assertIn("March 24", body)
        self.assertIn("March 30, 2026", body)
        self.assertIn("40", body)
        self.assertIn("$1120.00", body)
        self.assertIn("Lisa Wadley", body)

    def test_create_monthly_email_body(self):
        """Test monthly report email template."""
        body = create_monthly_email_body(
            name="Lisa Wadley",
            month_label="March 2026",
            total_hours=160,
            total_pay=4480.00
        )

        self.assertIn("March 2026", body)
        self.assertIn("160", body)
        self.assertIn("$4480.00", body)
        self.assertIn("Lisa Wadley", body)


class TestSendEmail(unittest.TestCase):
    """Test SES send_email wrapper function."""

    @patch('mail_service.boto3.client')
    def test_send_email_success(self, mock_boto3_client):
        """Test successful email send via SES."""
        # Mock SES client
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id-123'}
        mock_boto3_client.return_value = mock_ses

        # Send test email
        response = send_email(
            to_addresses=['test@example.com'],
            subject='Test Subject',
            body_text='Test body content',
            from_email='noreply@goinvoi.com'
        )

        # Verify SES was called
        self.assertTrue(mock_ses.send_raw_email.called)
        self.assertEqual(response['MessageId'], 'test-message-id-123')

    @patch('mail_service.boto3.client')
    def test_send_email_with_attachment(self, mock_boto3_client):
        """Test email send with PDF attachment."""
        # Mock SES client
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id-456'}
        mock_boto3_client.return_value = mock_ses

        # Send email with PDF attachment
        response = send_email(
            to_addresses=['test@example.com'],
            subject='Invoice Attached',
            body_text='Please find attached your invoice.',
            attachments=[
                {'filename': 'invoice.pdf', 'data': b'fake-pdf-content'}
            ],
            from_email='noreply@goinvoi.com'
        )

        # Verify SES was called
        self.assertTrue(mock_ses.send_raw_email.called)
        self.assertEqual(response['MessageId'], 'test-message-id-456')

    def test_send_email_empty_recipients(self):
        """Test that empty to_addresses raises ValueError."""
        with self.assertRaises(ValueError):
            send_email(
                to_addresses=[],
                subject='Test',
                body_text='Test',
                from_email='noreply@goinvoi.com'
            )


class TestSendWeeklyEmail(unittest.TestCase):
    """Test send_weekly_email wrapper function."""

    @patch('mail_service.boto3.client')
    def test_send_weekly_email_success(self, mock_boto3_client):
        """Test successful weekly invoice email send."""
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
        self.assertTrue(mock_ses.send_raw_email.called)
        self.assertEqual(response['MessageId'], 'weekly-msg-id')

        # Verify call arguments include display name
        call_args = mock_ses.send_raw_email.call_args
        self.assertIn('Lisa Wadley', call_args[1]['Source'])

    @patch('mail_service.boto3.client')
    def test_send_weekly_email_with_logs(self, mock_boto3_client):
        """Test weekly invoice email with service logs attached."""
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
        self.assertTrue(mock_ses.send_raw_email.called)
        self.assertEqual(response['MessageId'], 'weekly-with-logs-msg-id')

    def test_send_weekly_email_logs_without_data(self):
        """Test that include_logs=True without log data raises ValueError."""
        with self.assertRaises(ValueError):
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
        """Test that empty to_addresses raises ValueError."""
        with self.assertRaises(ValueError):
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
        """Test that missing pdf_data raises ValueError."""
        with self.assertRaises(ValueError):
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


class TestSendMonthlyEmail(unittest.TestCase):
    """Test send_monthly_email wrapper function."""

    @patch('mail_service.boto3.client')
    def test_send_monthly_email_success(self, mock_boto3_client):
        """Test successful monthly report email send."""
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
        self.assertTrue(mock_ses.send_raw_email.called)
        self.assertEqual(response['MessageId'], 'monthly-msg-id')

        # Verify call arguments include display name
        call_args = mock_ses.send_raw_email.call_args
        self.assertIn('Lisa Wadley', call_args[1]['Source'])

    def test_send_monthly_email_empty_recipients(self):
        """Test that empty to_addresses raises ValueError."""
        with self.assertRaises(ValueError):
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
        """Test that missing pdf_data raises ValueError."""
        with self.assertRaises(ValueError):
            send_monthly_email(
                to_addresses=['client@example.com'],
                user_name='Lisa Wadley',
                month_label='March 2026',
                total_hours=160,
                total_pay=4480.00,
                pdf_data=None,
                pdf_filename='RPT-2026-03.pdf'
            )


if __name__ == '__main__':
    unittest.main()
