import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.invoices import handler
from botocore.exceptions import ClientError


class TestPatchInvoiceStatus:
    """Tests for PATCH /api/invoices/{id}/status endpoint"""

    def test_patch_valid_status_updates_invoice(self):
        """PATCH with valid status should update invoice and return 200"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'},
            'body': json.dumps({'status': 'paid'})
        }

        # Mock existing invoice
        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'sent',
            'dueDate': '2026-03-30'
        }

        # Mock updated invoice
        mock_updated = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'paid',
            'paidAt': '2026-04-03T10:00:00'
        }

        with patch('functions.invoices.get_invoice', return_value=mock_invoice):
            with patch('functions.invoices.update_invoice_status', return_value=mock_updated):
                response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['invoiceId'] == 'INV-20260324'
        assert body['status'] == 'paid'
        assert 'paidAt' in body

    def test_patch_paid_status_sets_paidAt_timestamp(self):
        """PATCH with status=paid should set paidAt timestamp"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'},
            'body': json.dumps({'status': 'paid'})
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'sent'
        }

        mock_updated = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'paid',
            'paidAt': '2026-04-03T10:00:00.123456'
        }

        with patch('functions.invoices.get_invoice', return_value=mock_invoice):
            with patch('functions.invoices.update_invoice_status', return_value=mock_updated) as mock_update:
                response = handler(event, {})

        # Verify update_invoice_status was called with paidAt
        assert mock_update.called
        call_args = mock_update.call_args
        assert call_args[1]['status'] == 'paid'
        assert call_args[1]['paid_at'] is not None

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['paidAt'] == '2026-04-03T10:00:00.123456'

    def test_patch_overdue_calculated_when_sent_and_past_due(self):
        """PATCH with status=sent should auto-calculate overdue if past due date"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'},
            'body': json.dumps({'status': 'sent'})
        }

        # Mock invoice with past due date
        past_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'draft',
            'dueDate': past_date
        }

        mock_updated = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'overdue'  # Should be overdue, not sent
        }

        with patch('functions.invoices.get_invoice', return_value=mock_invoice):
            with patch('functions.invoices.update_invoice_status', return_value=mock_updated) as mock_update:
                response = handler(event, {})

        # Verify it called update with 'overdue' status, not 'sent'
        call_args = mock_update.call_args
        assert call_args[1]['status'] == 'overdue'

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'overdue'

    def test_patch_sent_not_overdue_when_within_due_date(self):
        """PATCH with status=sent should stay sent if within due date"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'},
            'body': json.dumps({'status': 'sent'})
        }

        # Mock invoice with future due date
        future_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'draft',
            'dueDate': future_date
        }

        mock_updated = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'sent'
        }

        with patch('functions.invoices.get_invoice', return_value=mock_invoice):
            with patch('functions.invoices.update_invoice_status', return_value=mock_updated) as mock_update:
                response = handler(event, {})

        # Verify it called update with 'sent' status, not 'overdue'
        call_args = mock_update.call_args
        assert call_args[1]['status'] == 'sent'

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'sent'

    def test_patch_invalid_status_returns_400(self):
        """PATCH with invalid status value should return 400"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'},
            'body': json.dumps({'status': 'invalid-status'})
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'draft'
        }

        with patch('functions.invoices.get_invoice', return_value=mock_invoice):
            response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'invalid-status' in body['error'].lower()

    def test_patch_missing_status_returns_400(self):
        """PATCH without status in body should return 400"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'},
            'body': json.dumps({})
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'status' in body['error'].lower()

    def test_patch_missing_invoice_id_returns_400(self):
        """PATCH without invoice ID in path should return 400"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {},
            'body': json.dumps({'status': 'paid'})
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'invoice id' in body['error'].lower()

    def test_patch_without_auth_returns_401(self):
        """PATCH without Authorization header should return 401"""
        event = {
            'requestContext': {'http': {'method': 'PATCH'}},
            'headers': {},
            'pathParameters': {'id': 'INV-20260324'},
            'body': json.dumps({'status': 'paid'})
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'authorization' in body['error'].lower()

    def test_patch_with_invalid_jwt_returns_401(self):
        """PATCH with invalid JWT (no claims) should return 401"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {}  # No JWT claims
            },
            'headers': {'Authorization': 'Bearer invalid-token'},
            'pathParameters': {'id': 'INV-20260324'},
            'body': json.dumps({'status': 'paid'})
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body

    def test_patch_non_existent_invoice_returns_404(self):
        """PATCH for non-existent invoice should return 404"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-99999999'},
            'body': json.dumps({'status': 'paid'})
        }

        # Mock invoice not found
        with patch('functions.invoices.get_invoice', return_value=None):
            response = handler(event, {})

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'not found' in body['error'].lower()

    def test_patch_handles_dynamodb_error(self):
        """PATCH should return 500 when DynamoDB operation fails"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'},
            'body': json.dumps({'status': 'paid'})
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'sent'
        }

        # Mock DynamoDB error
        mock_error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'UpdateItem'
        )

        with patch('functions.invoices.get_invoice', return_value=mock_invoice):
            with patch('functions.invoices.update_invoice_status', side_effect=mock_error):
                response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body

    def test_patch_invalid_json_returns_400(self):
        """PATCH with invalid JSON body should return 400"""
        event = {
            'requestContext': {
                'http': {'method': 'PATCH'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'},
            'body': 'invalid-json{'
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'json' in body['error'].lower()


class TestCORS:
    """Tests for CORS handling"""

    def test_options_request_returns_200(self):
        """OPTIONS preflight request should return 200 with CORS headers"""
        event = {
            'requestContext': {
                'http': {'method': 'OPTIONS'}
            },
            'headers': {'Authorization': 'Bearer valid-token'}
        }

        response = handler(event, {})

        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert 'Access-Control-Allow-Methods' in response['headers']
        assert 'Access-Control-Allow-Headers' in response['headers']
        assert 'PATCH' in response['headers']['Access-Control-Allow-Methods']
