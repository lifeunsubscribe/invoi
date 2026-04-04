import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.submit_weekly import handler, _calculate_due_date
from botocore.exceptions import ClientError


class TestSubmitWeekly:
    """Tests for POST /api/submit/weekly endpoint"""

    def test_submit_weekly_success(self):
        """POST with valid data should generate invoice and return metadata"""
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
                'hours': {
                    'Monday': 8,
                    'Tuesday': 8,
                    'Wednesday': 8,
                    'Thursday': 8,
                    'Friday': 8,
                    'Saturday': 0,
                    'Sunday': 0
                },
                'week': {
                    'start': '2026-03-24',
                    'end': '2026-03-30',
                    'invNum': 'INV-20260324'
                },
                'clientEmail': 'client@example.com',
                'accountantEmail': 'accountant@example.com',
                'saveOnly': True
            })
        }

        # Mock user config with all required fields
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'address': '123 Main St',
            'personalEmail': 'test@example.com',
            'rate': 28.00,
            'template': 'morning-light',
            'signatureFont': 'Dancing Script',
            'paymentTerms': 'receipt',
            'taxEnabled': False,
            'invoiceNumberConfig': {
                'prefix': 'INV',
                'includeYear': False,
                'separator': '-',
                'padding': 3,
                'nextNum': 1
            },
            'activeClientId': 'client-1',
            'clients': [
                {
                    'id': 'client-1',
                    'name': 'Test Client',
                    'email': 'client@example.com'
                }
            ]
        }

        # Mock PDF generation returning bytes
        mock_pdf_bytes = b'%PDF-1.4\nMock PDF content'

        with patch.dict(os.environ, {
            'USERS_TABLE': 'users-table',
            'INVOICES_TABLE': 'invoices-table',
            'SST_Resource_InvoiStorage_name': 'test-bucket'
        }):
            with patch('functions.submit_weekly.get_user', return_value=mock_user):
                with patch('functions.submit_weekly.generate_weekly_invoice', return_value=mock_pdf_bytes):
                    with patch('functions.submit_weekly.save_pdf_to_s3'):
                        with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                            with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                # Mock DynamoDB client for TransactWriteItems
                                mock_dynamodb_client = MagicMock()
                                mock_boto_client.return_value = mock_dynamodb_client

                                # Mock DynamoDB resource for put_item
                                mock_table = MagicMock()
                                mock_boto_resource.return_value.Table.return_value = mock_table

                                response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'invoiceNumber' in body
        assert 'invoiceId' in body
        assert body['invoiceId'] == 'INV-20260324'
        assert 's3Key' in body
        assert 'users/user-123/weekly/INV-20260324.pdf' in body['s3Key']
        assert body['status'] == 'draft'
        assert body['totalHours'] == 40
        assert body['totalPay'] == 1120.0

    def test_submit_weekly_missing_hours(self):
        """POST without hours should return 400"""
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
                'week': {
                    'start': '2026-03-24',
                    'end': '2026-03-30',
                    'invNum': 'INV-20260324'
                }
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'hours' in body['error'].lower()

    def test_submit_weekly_invalid_hours(self):
        """POST with negative hours should return 400"""
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
                'hours': {
                    'Monday': -5,  # Invalid negative hours
                    'Tuesday': 8
                },
                'week': {
                    'start': '2026-03-24',
                    'end': '2026-03-30',
                    'invNum': 'INV-20260324'
                }
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'non-negative' in body['error']

    def test_submit_weekly_missing_auth(self):
        """POST without Authorization header should return 401"""
        event = {
            'requestContext': {'http': {'method': 'POST'}},
            'headers': {},
            'body': json.dumps({
                'hours': {'Monday': 8},
                'week': {'start': '2026-03-24', 'end': '2026-03-30', 'invNum': 'INV-20260324'}
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Authorization' in body['error']

    def test_submit_weekly_user_not_found(self):
        """POST with valid auth but missing user config should return 500"""
        event = {
            'requestContext': {
                'http': {'method': 'POST'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-999'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'hours': {'Monday': 8},
                'week': {'start': '2026-03-24', 'end': '2026-03-30', 'invNum': 'INV-20260324'}
            })
        }

        with patch('functions.submit_weekly.get_user', return_value=None):
            response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'configuration not found' in body['error'].lower()

    def test_submit_weekly_incomplete_profile(self):
        """POST with incomplete user profile should return 400"""
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
                'hours': {'Monday': 8},
                'week': {'start': '2026-03-24', 'end': '2026-03-30', 'invNum': 'INV-20260324'}
            })
        }

        # Mock user with missing required fields
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            # Missing: address, personalEmail, rate
        }

        with patch('functions.submit_weekly.get_user', return_value=mock_user):
            response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'complete your profile' in body['error'].lower()

    def test_submit_weekly_no_active_client(self):
        """POST with no active client should return 400"""
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
                'hours': {'Monday': 8},
                'week': {'start': '2026-03-24', 'end': '2026-03-30', 'invNum': 'INV-20260324'}
            })
        }

        # Mock user with no active client
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'address': '123 Main St',
            'personalEmail': 'test@example.com',
            'rate': 28.00,
            'clients': []  # No clients
        }

        with patch('functions.submit_weekly.get_user', return_value=mock_user):
            response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'active client' in body['error'].lower()

    def test_submit_weekly_with_tax(self):
        """POST with tax enabled should calculate tax correctly"""
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
                'hours': {'Monday': 10, 'Tuesday': 10, 'Wednesday': 10, 'Thursday': 10, 'Friday': 10, 'Saturday': 0, 'Sunday': 0},
                'week': {'start': '2026-03-24', 'end': '2026-03-30', 'invNum': 'INV-20260324'},
                'saveOnly': True
            })
        }

        # Mock user with tax enabled
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'address': '123 Main St',
            'personalEmail': 'test@example.com',
            'rate': 30.00,
            'taxEnabled': True,
            'taxRate': 8.25,  # 8.25% tax
            'template': 'morning-light',
            'signatureFont': '',
            'paymentTerms': 'receipt',
            'invoiceNumberConfig': {
                'prefix': 'INV',
                'nextNum': 1,
                'separator': '-',
                'padding': 3
            },
            'activeClientId': 'client-1',
            'clients': [{'id': 'client-1', 'name': 'Test Client'}]
        }

        mock_pdf_bytes = b'%PDF-1.4\nMock PDF content'

        with patch.dict(os.environ, {
            'USERS_TABLE': 'users-table',
            'INVOICES_TABLE': 'invoices-table',
            'SST_Resource_InvoiStorage_name': 'test-bucket'
        }):
            with patch('functions.submit_weekly.get_user', return_value=mock_user):
                with patch('functions.submit_weekly.generate_weekly_invoice', return_value=mock_pdf_bytes):
                    with patch('functions.submit_weekly.save_pdf_to_s3'):
                        with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                            with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                mock_dynamodb_client = MagicMock()
                                mock_boto_client.return_value = mock_dynamodb_client
                                mock_table = MagicMock()
                                mock_boto_resource.return_value.Table.return_value = mock_table

                                response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        # 50 hours × $30 = $1500 subtotal
        # $1500 × 8.25% = $123.75 tax
        # Total = $1623.75
        assert body['totalPay'] == 1623.75

    def test_cors_preflight(self):
        """OPTIONS request should return 200 with CORS headers"""
        event = {
            'requestContext': {'http': {'method': 'OPTIONS'}},
            'headers': {}
        }

        response = handler(event, {})

        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert response['headers']['Access-Control-Allow-Origin'] == '*'

    def test_calculate_due_date_receipt(self):
        """Due date calculation for 'receipt' payment terms"""
        invoice_date = datetime(2026, 3, 24)
        due_date = _calculate_due_date(invoice_date, 'receipt')
        assert due_date == '2026-03-24'

    def test_calculate_due_date_net7(self):
        """Due date calculation for 'net7' payment terms"""
        invoice_date = datetime(2026, 3, 24)
        due_date = _calculate_due_date(invoice_date, 'net7')
        assert due_date == '2026-03-31'

    def test_calculate_due_date_net30(self):
        """Due date calculation for 'net30' payment terms"""
        invoice_date = datetime(2026, 3, 24)
        due_date = _calculate_due_date(invoice_date, 'net30')
        assert due_date == '2026-04-23'

    def test_invalid_json_body(self):
        """POST with invalid JSON should return 400"""
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
            'body': 'not valid json {'
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'JSON' in body['error']

    def test_submit_weekly_transaction_cancelled(self):
        """POST should handle TransactionCanceledException gracefully"""
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
                'hours': {
                    'Monday': 8,
                    'Tuesday': 8,
                    'Wednesday': 8,
                    'Thursday': 8,
                    'Friday': 8,
                    'Saturday': 0,
                    'Sunday': 0
                },
                'week': {
                    'start': '2026-03-24',
                    'end': '2026-03-30',
                    'invNum': 'INV-20260324'
                },
                'clientEmail': 'client@example.com',
                'accountantEmail': 'accountant@example.com',
                'saveOnly': True
            })
        }

        # Mock user config
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'address': '123 Main St',
            'personalEmail': 'test@example.com',
            'rate': 28.00,
            'template': 'morning-light',
            'signatureFont': 'Dancing Script',
            'paymentTerms': 'receipt',
            'taxEnabled': False,
            'invoiceNumberConfig': {
                'prefix': 'INV',
                'includeYear': False,
                'separator': '-',
                'padding': 3,
                'nextNum': 1
            },
            'activeClientId': 'client-1',
            'clients': [
                {
                    'id': 'client-1',
                    'name': 'Test Client',
                    'email': 'client@example.com'
                }
            ]
        }

        # Mock PDF generation returning bytes
        mock_pdf_bytes = b'%PDF-1.4\nMock PDF content'

        # Mock TransactionCanceledException
        transaction_error = ClientError(
            {
                'Error': {
                    'Code': 'TransactionCanceledException',
                    'Message': 'Transaction cancelled'
                },
                'CancellationReasons': [
                    {'Code': 'ConditionalCheckFailed', 'Message': 'Invoice already exists'}
                ]
            },
            'TransactWriteItems'
        )

        with patch.dict(os.environ, {
            'USERS_TABLE': 'users-table',
            'INVOICES_TABLE': 'invoices-table',
            'SST_Resource_InvoiStorage_name': 'test-bucket'
        }):
            with patch('functions.submit_weekly.get_user', return_value=mock_user):
                with patch('functions.submit_weekly.generate_weekly_invoice', return_value=mock_pdf_bytes):
                    with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                        # Mock DynamoDB client to raise TransactionCanceledException
                        mock_dynamodb_client = MagicMock()
                        mock_dynamodb_client.transact_write_items.side_effect = transaction_error
                        mock_boto_client.return_value = mock_dynamodb_client

                        response = handler(event, {})

        # Should return 500 error when transaction is cancelled
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
