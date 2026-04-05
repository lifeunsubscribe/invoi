"""
Unit tests for resend.py Lambda function

Tests bulk resend functionality for invoices.
"""
import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.resend import handler, _create_resend_email_body, _create_monthly_resend_email_body, _extract_user_id_from_token


class TestResendEmailBodies:
    """Test email body generation functions"""

    def test_create_resend_email_body(self):
        """Test weekly resend email body generation"""
        body = _create_resend_email_body(
            name="Lisa Wadley",
            week_start="2026-03-24",
            week_end="2026-03-30",
            total_hours=40,
            total_pay=1120.00
        )

        assert "Lisa Wadley" in body
        assert "2026-03-24" in body
        assert "2026-03-30" in body
        assert "40" in body
        assert "$1120.00" in body
        assert "(Resent)" in body
        assert "goinvoi.com" in body

    def test_create_monthly_resend_email_body(self):
        """Test monthly resend email body generation"""
        body = _create_monthly_resend_email_body(
            name="Lisa Wadley",
            month_label="March 2026",
            total_hours=160,
            total_pay=4480.00
        )

        assert "Lisa Wadley" in body
        assert "March 2026" in body
        assert "160" in body
        assert "$4480.00" in body
        assert "(Resent)" in body
        assert "goinvoi.com" in body


class TestExtractUserId:
    """Test JWT token user ID extraction"""

    def test_extract_user_id_from_cognito_jwt(self):
        """Test extracting userId from Cognito JWT claims (API Gateway v2)"""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'sub': 'user-123'
                        }
                    }
                }
            }
        }

        user_id = _extract_user_id_from_token(event)
        assert user_id == 'user-123'

    def test_extract_user_id_from_lambda_authorizer(self):
        """Test extracting userId from Lambda authorizer (API Gateway v1)"""
        event = {
            'requestContext': {
                'authorizer': {
                    'claims': {
                        'sub': 'user-456'
                    }
                }
            }
        }

        user_id = _extract_user_id_from_token(event)
        assert user_id == 'user-456'

    def test_extract_user_id_missing_claims(self):
        """Test extraction returns None when claims are missing"""
        event = {'requestContext': {}}
        user_id = _extract_user_id_from_token(event)
        assert user_id is None


class TestResendHandler:
    """Test resend Lambda handler"""

    @patch('functions.resend.get_user')
    @patch('functions.resend.get_invoice')
    @patch('functions.resend.send_email')
    @patch('functions.resend.s3_client')
    def test_successful_resend_single_invoice(self, mock_s3, mock_send_email, mock_get_invoice, mock_get_user):
        """Test successful resend of a single invoice"""
        # Mock user config
        mock_get_user.return_value = {
            'userId': 'user-123',
            'name': 'Lisa Wadley',
            'clients': [
                {'id': 'client-abc', 'email': 'client@example.com'}
            ],
            'accountantEmail': 'accountant@example.com'
        }

        # Mock invoice
        mock_get_invoice.return_value = {
            'userId': 'user-123',
            'invoiceId': 'INV-001',
            'invoiceNumber': 'INV-047',
            'clientId': 'client-abc',
            'type': 'weekly',
            'status': 'sent',
            'weekStart': '2026-03-24',
            'weekEnd': '2026-03-30',
            'totalHours': 40,
            'totalPay': 1120.0,
            'pdfKey': 'users/user-123/invoices/INV-001.pdf'
        }

        # Mock S3 PDF fetch
        mock_pdf_obj = MagicMock()
        mock_pdf_obj['Body'].read.return_value = b'fake-pdf-content'
        mock_s3.get_object.return_value = mock_pdf_obj

        # Mock send_email
        mock_send_email.return_value = {'MessageId': 'msg-123'}

        # Create event
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                },
                'http': {'method': 'POST'}
            },
            'headers': {'Authorization': 'Bearer token'},
            'body': json.dumps({
                'invoiceIds': ['INV-001']
            })
        }

        # Set environment variable
        os.environ['InvoiStorage'] = 'test-bucket'

        # Call handler
        response = handler(event, {})

        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['successful'] == 1
        assert body['failed'] == 0
        assert body['total'] == 1

        # Verify email was sent
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert 'client@example.com' in call_args[1]['to_addresses']
        assert 'accountant@example.com' in call_args[1]['to_addresses']

    @patch('functions.resend.get_user')
    @patch('functions.resend.get_invoice')
    def test_resend_draft_invoice_fails(self, mock_get_invoice, mock_get_user):
        """Test that resending a draft invoice fails"""
        # Mock user config
        mock_get_user.return_value = {
            'userId': 'user-123',
            'name': 'Lisa Wadley',
            'clients': []
        }

        # Mock draft invoice
        mock_get_invoice.return_value = {
            'userId': 'user-123',
            'invoiceId': 'INV-001',
            'status': 'draft'  # Draft status should fail
        }

        # Create event
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                },
                'http': {'method': 'POST'}
            },
            'headers': {'Authorization': 'Bearer token'},
            'body': json.dumps({
                'invoiceIds': ['INV-001']
            })
        }

        os.environ['InvoiStorage'] = 'test-bucket'

        # Call handler
        response = handler(event, {})

        # Verify response shows failure
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['successful'] == 0
        assert body['failed'] == 1
        assert 'Cannot resend draft invoice' in body['failedDetails'][0]

    def test_resend_missing_auth_header(self):
        """Test that missing auth header returns 401"""
        event = {
            'requestContext': {'http': {'method': 'POST'}},
            'headers': {},
            'body': json.dumps({'invoiceIds': ['INV-001']})
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'Missing Authorization header' in body['error']

    def test_resend_invalid_request_body(self):
        """Test that invalid request body returns 400"""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                },
                'http': {'method': 'POST'}
            },
            'headers': {'Authorization': 'Bearer token'},
            'body': json.dumps({})  # Missing invoiceIds
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'invoiceIds must be a non-empty array' in body['error']

    def test_resend_too_many_invoices(self):
        """Test that requesting too many invoices returns 400"""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                },
                'http': {'method': 'POST'}
            },
            'headers': {'Authorization': 'Bearer token'},
            'body': json.dumps({
                'invoiceIds': [f'INV-{i:03d}' for i in range(51)]  # 51 invoices (max is 50)
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Cannot resend more than' in body['error']

    @patch('functions.resend.get_user')
    @patch('functions.resend.get_invoice')
    def test_lambda_response_has_no_cors_headers(self, mock_get_invoice, mock_get_user):
        """Lambda responses should not include CORS headers (API Gateway handles them)"""
        event = {
            'requestContext': {
                'http': {'method': 'POST'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer token'},
            'body': json.dumps({
                'invoiceIds': ['INV-001']
            })
        }

        # Mock user config
        mock_get_user.return_value = {
            'userId': 'user-123',
            'name': 'Lisa Wadley',
            'clients': []
        }

        # Mock invoice not found to get quick response
        mock_get_invoice.return_value = None

        os.environ['InvoiStorage'] = 'test-bucket'

        response = handler(event, {})

        assert response['statusCode'] == 200
        # Lambda should NOT set CORS headers - API Gateway handles them
        assert 'Access-Control-Allow-Origin' not in response['headers']
        assert 'Access-Control-Allow-Methods' not in response['headers']
        assert 'Access-Control-Allow-Headers' not in response['headers']
        # But Content-Type should still be set
        assert response['headers']['Content-Type'] == 'application/json'
