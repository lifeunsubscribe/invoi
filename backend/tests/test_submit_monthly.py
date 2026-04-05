import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.submit_monthly import handler
from botocore.exceptions import ClientError


class TestSubmitMonthly:
    """Tests for POST /api/submit/monthly endpoint"""

    def test_submit_monthly_with_send(self):
        """POST with send=True should send email and update status to 'sent'"""
        event = {
            'requestContext': {
                'http': {'method': 'POST'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'year': 2026,
                'month': 3,
                'send': True,
                'accountantEmail': 'accountant@example.com'
            })
        }

        # Mock user config
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'rate': 28.00,
            'template': 'morning-light',
            'signatureFont': 'Dancing Script'
        }

        # Mock weekly invoices
        mock_weekly_invoices = [
            {
                'invoiceId': 'INV-20260301',
                'weekStart': '2026-03-01',
                'weekEnd': '2026-03-07',
                'totalHours': 40
            },
            {
                'invoiceId': 'INV-20260308',
                'weekStart': '2026-03-08',
                'weekEnd': '2026-03-14',
                'totalHours': 38
            }
        ]

        # Mock PDF generation
        mock_pdf_bytes = b'%PDF-1.4\nMock PDF content'

        with patch.dict(os.environ, {
            'SST_Resource_InvoiStorage_name': 'test-bucket'
        }):
            with patch('functions.submit_monthly.get_user', return_value=mock_user):
                with patch('functions.submit_monthly.query_invoices', return_value=mock_weekly_invoices):
                    with patch('functions.submit_monthly.generate_monthly_report', return_value=mock_pdf_bytes):
                        with patch('functions.submit_monthly.save_pdf_to_s3'):
                            with patch('functions.submit_monthly.put_invoice') as mock_put_invoice:
                                with patch('functions.submit_monthly.send_monthly_email') as mock_send_email:
                                    response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'sent' in body
        assert body['sent'] == ['accountant@example.com']
        assert body['status'] == 'sent'

        # Verify email was sent with correct parameters
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[1]['to_addresses'] == ['accountant@example.com']
        assert call_args[1]['user_name'] == 'Test User'

        # Verify put_invoice called twice (initial save + status update after send)
        assert mock_put_invoice.call_count == 2

    def test_submit_monthly_without_send(self):
        """POST with send=False should save as draft without sending email"""
        event = {
            'requestContext': {
                'http': {'method': 'POST'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'year': 2026,
                'month': 3,
                'send': False,
                'accountantEmail': 'accountant@example.com'
            })
        }

        # Mock user config
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'rate': 28.00,
            'template': 'morning-light',
            'signatureFont': 'Dancing Script'
        }

        # Mock weekly invoices
        mock_weekly_invoices = [
            {
                'invoiceId': 'INV-20260301',
                'weekStart': '2026-03-01',
                'weekEnd': '2026-03-07',
                'totalHours': 40
            }
        ]

        # Mock PDF generation
        mock_pdf_bytes = b'%PDF-1.4\nMock PDF content'

        with patch.dict(os.environ, {
            'SST_Resource_InvoiStorage_name': 'test-bucket'
        }):
            with patch('functions.submit_monthly.get_user', return_value=mock_user):
                with patch('functions.submit_monthly.query_invoices', return_value=mock_weekly_invoices):
                    with patch('functions.submit_monthly.generate_monthly_report', return_value=mock_pdf_bytes):
                        with patch('functions.submit_monthly.save_pdf_to_s3'):
                            with patch('functions.submit_monthly.put_invoice') as mock_put_invoice:
                                with patch('functions.submit_monthly.send_monthly_email') as mock_send_email:
                                    response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'sent' in body
        assert body['sent'] == []
        assert body['status'] == 'draft'

        # Verify email was NOT sent
        mock_send_email.assert_not_called()

    def test_submit_monthly_missing_year(self):
        """POST without year should return 400"""
        event = {
            'requestContext': {
                'http': {'method': 'POST'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'month': 3
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'year' in body['error'].lower()

    def test_submit_monthly_no_weekly_invoices(self):
        """POST for month with no weekly invoices should return 400"""
        event = {
            'requestContext': {
                'http': {'method': 'POST'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'year': 2026,
                'month': 3,
                'send': True,
                'accountantEmail': 'accountant@example.com'
            })
        }

        # Mock user config
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'rate': 28.00,
            'template': 'morning-light'
        }

        # Mock empty weekly invoices
        mock_weekly_invoices = []

        with patch('functions.submit_monthly.get_user', return_value=mock_user):
            with patch('functions.submit_monthly.query_invoices', return_value=mock_weekly_invoices):
                response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'no weekly invoices' in body['error'].lower()

    def test_submit_monthly_email_failure_returns_warning(self):
        """POST with email failure should return success with warning"""
        event = {
            'requestContext': {
                'http': {'method': 'POST'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'year': 2026,
                'month': 3,
                'send': True,
                'accountantEmail': 'accountant@example.com'
            })
        }

        # Mock user config
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'rate': 28.00,
            'template': 'morning-light'
        }

        # Mock weekly invoices
        mock_weekly_invoices = [
            {
                'invoiceId': 'INV-20260301',
                'weekStart': '2026-03-01',
                'weekEnd': '2026-03-07',
                'totalHours': 40
            }
        ]

        # Mock PDF generation
        mock_pdf_bytes = b'%PDF-1.4\nMock PDF content'

        with patch.dict(os.environ, {
            'SST_Resource_InvoiStorage_name': 'test-bucket'
        }):
            with patch('functions.submit_monthly.get_user', return_value=mock_user):
                with patch('functions.submit_monthly.query_invoices', return_value=mock_weekly_invoices):
                    with patch('functions.submit_monthly.generate_monthly_report', return_value=mock_pdf_bytes):
                        with patch('functions.submit_monthly.save_pdf_to_s3'):
                            with patch('functions.submit_monthly.put_invoice'):
                                with patch('functions.submit_monthly.send_monthly_email', side_effect=Exception('SES error')):
                                    response = handler(event, {})

        # Should return 200 with warning, not error
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'emailWarning' in body
        assert 'SES error' in body['emailWarning']
        assert body['sent'] == []
        assert body['status'] == 'draft'  # Status should remain draft since email failed

    def test_submit_monthly_idempotency_returns_existing_report(self):
        """POST for already-generated report should return existing report without regeneration"""
        event = {
            'requestContext': {
                'http': {'method': 'POST'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'year': 2026,
                'month': 3,
                'send': False
            })
        }

        # Mock user config
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'rate': 28.00,
            'template': 'morning-light'
        }

        # Mock existing report
        existing_report = {
            'userId': 'user-123',
            'invoiceId': 'RPT-2026-03',
            'type': 'monthly',
            'status': 'sent',
            'year': 2026,
            'month': 3,
            'monthLabel': 'March 2026',
            'weekCount': 4,
            'totalHours': 160,
            'rate': 28.00,
            'totalPay': 4480.00,
            'pdfKey': 'users/user-123/reports/RPT-2026-03.pdf',
            'createdAt': '2026-03-31T10:00:00Z'
        }

        with patch('functions.submit_monthly.get_user', return_value=mock_user):
            with patch('functions.submit_monthly.get_invoice', return_value=existing_report):
                with patch('functions.submit_monthly.query_invoices') as mock_query:
                    with patch('functions.submit_monthly.generate_monthly_report') as mock_generate:
                        response = handler(event, {})

        # Should return 200 with existing report data
        assert response['statusCode'] == 200
        body = json.loads(response['body'])

        # Verify existing report data is returned
        assert body['reportId'] == 'RPT-2026-03'
        assert body['s3Key'] == 'users/user-123/reports/RPT-2026-03.pdf'
        assert body['monthLabel'] == 'March 2026'
        assert body['totalHours'] == 160
        assert body['totalPay'] == 4480.00
        assert body['weekCount'] == 4
        assert body['status'] == 'sent'
        assert body['alreadyExists'] is True

        # Verify PDF was NOT regenerated (functions not called)
        mock_query.assert_not_called()
        mock_generate.assert_not_called()

    def test_submit_monthly_partial_corrupted_report_returns_none_values(self):
        """POST for partial/corrupted existing report should return None values for missing fields"""
        event = {
            'requestContext': {
                'http': {'method': 'POST'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'year': 2026,
                'month': 3,
                'send': False
            })
        }

        # Mock user config
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'rate': 28.00,
            'template': 'morning-light'
        }

        # Mock partial/corrupted existing report - missing critical fields
        # This simulates a scenario where the database write was interrupted
        # or the report was created before certain fields were added
        corrupted_report = {
            'userId': 'user-123',
            'invoiceId': 'RPT-2026-03',
            'type': 'monthly',
            'pdfKey': 'users/user-123/reports/RPT-2026-03.pdf',
            'createdAt': '2026-03-31T10:00:00Z'
            # Missing: status, year, month, monthLabel, weekCount, totalHours, totalPay
        }

        with patch('functions.submit_monthly.get_user', return_value=mock_user):
            with patch('functions.submit_monthly.get_invoice', return_value=corrupted_report):
                with patch('functions.submit_monthly.query_invoices') as mock_query:
                    with patch('functions.submit_monthly.generate_monthly_report') as mock_generate:
                        response = handler(event, {})

        # Should return 200 with the corrupted report data
        assert response['statusCode'] == 200
        body = json.loads(response['body'])

        # Verify basic fields are returned
        assert body['reportId'] == 'RPT-2026-03'
        assert body['s3Key'] == 'users/user-123/reports/RPT-2026-03.pdf'
        assert body['alreadyExists'] is True

        # Verify missing fields return None (this is the bug scenario)
        assert body['monthLabel'] is None
        assert body['totalHours'] is None
        assert body['totalPay'] is None
        assert body['weekCount'] is None
        assert body['status'] is None

        # Verify PDF was NOT regenerated (idempotency behavior maintained)
        mock_query.assert_not_called()
        mock_generate.assert_not_called()
