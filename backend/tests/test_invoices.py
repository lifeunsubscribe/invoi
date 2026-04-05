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

    def test_patch_other_users_invoice_returns_403(self):
        """PATCH for invoice belonging to another user should return 403"""
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

        # Mock invoice that belongs to a different user
        mock_invoice = {
            'userId': 'user-456',  # Different user
            'invoiceId': 'INV-20260324',
            'status': 'sent'
        }

        with patch('functions.invoices.get_invoice', return_value=mock_invoice):
            response = handler(event, {})

        assert response['statusCode'] == 403
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'unauthorized' in body['error'].lower()

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


class TestGetInvoicesList:
    """Tests for GET /api/invoices endpoint"""

    def test_get_list_returns_all_user_invoices(self):
        """GET /api/invoices should return all invoices for authenticated user"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': None
        }

        mock_invoices = [
            {'userId': 'user-123', 'invoiceId': 'INV-20260324', 'status': 'sent', 'totalPay': 1120.00},
            {'userId': 'user-123', 'invoiceId': 'INV-20260331', 'status': 'paid', 'totalPay': 1200.00},
        ]

        with patch('functions.invoices.query_invoices', return_value=mock_invoices):
            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'invoices' in body
        assert 'pagination' in body
        assert len(body['invoices']) == 2
        assert body['pagination']['total'] == 2

    def test_get_list_filters_by_single_status(self):
        """GET /api/invoices?status=sent should filter by status"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': {'status': 'sent'}
        }

        mock_invoices = [
            {'userId': 'user-123', 'invoiceId': 'INV-20260324', 'status': 'sent'},
        ]

        with patch('functions.invoices.query_invoices', return_value=mock_invoices) as mock_query:
            response = handler(event, {})

        # Verify query_invoices was called with status filter
        call_args = mock_query.call_args
        assert call_args[0][0] == 'user-123'
        assert call_args[0][1]['status'] == 'sent'

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert len(body['invoices']) == 1
        assert body['invoices'][0]['status'] == 'sent'

    def test_get_list_filters_by_multiple_statuses(self):
        """GET /api/invoices?status=sent,paid should filter by multiple statuses"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': {'status': 'sent,paid'}
        }

        # Mock all invoices (before application-level filtering)
        mock_all_invoices = [
            {'userId': 'user-123', 'invoiceId': 'INV-20260324', 'status': 'sent'},
            {'userId': 'user-123', 'invoiceId': 'INV-20260331', 'status': 'paid'},
            {'userId': 'user-123', 'invoiceId': 'INV-20260307', 'status': 'draft'},
        ]

        with patch('functions.invoices.query_invoices', return_value=mock_all_invoices):
            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        # Should only return sent and paid, not draft
        assert len(body['invoices']) == 2
        statuses = {inv['status'] for inv in body['invoices']}
        assert statuses == {'sent', 'paid'}

    def test_get_list_filters_by_client_id(self):
        """GET /api/invoices?clientId=client_abc should filter by client"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': {'clientId': 'client_abc'}
        }

        mock_invoices = [
            {'userId': 'user-123', 'invoiceId': 'INV-20260324', 'clientId': 'client_abc'},
        ]

        with patch('functions.invoices.query_invoices', return_value=mock_invoices) as mock_query:
            response = handler(event, {})

        # Verify query_invoices was called with clientId filter
        call_args = mock_query.call_args
        assert call_args[0][1]['clientId'] == 'client_abc'

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert len(body['invoices']) == 1

    def test_get_list_filters_by_date_range(self):
        """GET /api/invoices?start=2026-03-01&end=2026-03-31 should filter by date range"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': {
                'start': '2026-03-01',
                'end': '2026-03-31'
            }
        }

        mock_invoices = [
            {'userId': 'user-123', 'invoiceId': 'INV-20260324'},
        ]

        with patch('functions.invoices.query_invoices', return_value=mock_invoices) as mock_query:
            response = handler(event, {})

        # Verify date range was converted to invoiceId range
        call_args = mock_query.call_args
        filters = call_args[0][1]
        assert filters['invoiceId_start'] == 'INV-20260301'
        assert filters['invoiceId_end'] == 'INV-20260331'

        assert response['statusCode'] == 200

    def test_get_list_invalid_start_date_returns_400(self):
        """GET /api/invoices?start=invalid should return 400"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': {'start': 'invalid-date'}
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'date format' in body['error'].lower()

    def test_get_list_pagination_with_limit_and_offset(self):
        """GET /api/invoices?limit=2&offset=1 should paginate results"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': {'limit': '2', 'offset': '1'}
        }

        mock_invoices = [
            {'invoiceId': 'INV-001'},
            {'invoiceId': 'INV-002'},
            {'invoiceId': 'INV-003'},
            {'invoiceId': 'INV-004'},
        ]

        with patch('functions.invoices.query_invoices', return_value=mock_invoices):
            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        # Should return 2 items starting from index 1
        assert len(body['invoices']) == 2
        assert body['invoices'][0]['invoiceId'] == 'INV-002'
        assert body['invoices'][1]['invoiceId'] == 'INV-003'
        assert body['pagination']['total'] == 4
        assert body['pagination']['limit'] == 2
        assert body['pagination']['offset'] == 1
        assert body['pagination']['hasMore'] is True

    def test_get_list_pagination_defaults(self):
        """GET /api/invoices without pagination params should use defaults"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': None
        }

        mock_invoices = [{'invoiceId': f'INV-{i:03d}'} for i in range(1, 51)]

        with patch('functions.invoices.query_invoices', return_value=mock_invoices):
            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        # Default limit is 100, offset is 0
        assert body['pagination']['limit'] == 100
        assert body['pagination']['offset'] == 0
        assert body['pagination']['total'] == 50

    def test_get_list_invalid_limit_returns_400(self):
        """GET /api/invoices?limit=5000 should return 400 (exceeds max)"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': {'limit': '5000'}
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'limit' in body['error'].lower()

    def test_get_list_without_auth_returns_401(self):
        """GET /api/invoices without Authorization should return 401"""
        event = {
            'requestContext': {'http': {'method': 'GET'}},
            'headers': {},
            'queryStringParameters': None
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'authorization' in body['error'].lower()

    def test_get_list_handles_dynamodb_error(self):
        """GET /api/invoices should return 500 when DynamoDB fails"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': None
        }

        mock_error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'Query'
        )

        with patch('functions.invoices.query_invoices', side_effect=mock_error):
            response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body


class TestGetSingleInvoice:
    """Tests for GET /api/invoices/{id} endpoint"""

    def test_get_single_invoice_returns_full_metadata(self):
        """GET /api/invoices/{id} should return full invoice metadata"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'}
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'sent',
            'totalPay': 1120.00,
            'clientId': 'client_abc',
            'weekStart': '2026-03-24',
            'weekEnd': '2026-03-30'
        }

        with patch('functions.invoices.get_invoice', return_value=mock_invoice):
            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['invoiceId'] == 'INV-20260324'
        assert body['status'] == 'sent'
        assert body['totalPay'] == 1120.00

    def test_get_single_invoice_not_found_returns_404(self):
        """GET /api/invoices/{id} for non-existent invoice should return 404"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-99999999'}
        }

        with patch('functions.invoices.get_invoice', return_value=None):
            response = handler(event, {})

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'not found' in body['error'].lower()

    def test_get_single_invoice_other_user_returns_403(self):
        """GET /api/invoices/{id} for another user's invoice should return 403"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'}
        }

        # Mock invoice belonging to different user
        mock_invoice = {
            'userId': 'user-456',  # Different user
            'invoiceId': 'INV-20260324'
        }

        with patch('functions.invoices.get_invoice', return_value=mock_invoice):
            response = handler(event, {})

        assert response['statusCode'] == 403
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'unauthorized' in body['error'].lower()

    def test_get_single_invoice_without_auth_returns_401(self):
        """GET /api/invoices/{id} without Authorization should return 401"""
        event = {
            'requestContext': {'http': {'method': 'GET'}},
            'headers': {},
            'pathParameters': {'id': 'INV-20260324'}
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body

    def test_get_single_invoice_handles_dynamodb_error(self):
        """GET /api/invoices/{id} should return 500 when DynamoDB fails"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'pathParameters': {'id': 'INV-20260324'}
        }

        mock_error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'GetItem'
        )

        with patch('functions.invoices.get_invoice', side_effect=mock_error):
            response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body


class TestCORS:
    """Tests for CORS handling

    Note: CORS is now handled by API Gateway (configured in sst.config.ts).
    Lambda functions no longer set CORS headers directly.
    API Gateway automatically adds CORS headers based on the configuration.
    """

    def test_lambda_response_has_no_cors_headers(self):
        """Lambda responses should not include CORS headers (API Gateway handles them)"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'queryStringParameters': None
        }

        mock_invoices = [
            {'userId': 'user-123', 'invoiceId': 'INV-20260324', 'status': 'sent', 'totalPay': 1120.00},
        ]

        with patch('functions.invoices.query_invoices', return_value=mock_invoices):
            response = handler(event, {})

        assert response['statusCode'] == 200
        # Lambda should NOT set CORS headers - API Gateway handles them
        assert 'Access-Control-Allow-Origin' not in response['headers']
        assert 'Access-Control-Allow-Methods' not in response['headers']
        assert 'Access-Control-Allow-Headers' not in response['headers']
        # But Content-Type should still be set
        assert response['headers']['Content-Type'] == 'application/json'
