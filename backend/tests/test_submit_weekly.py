import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.submit_weekly import handler, _calculate_due_date, _populate_hours_from_default_shift, _increment_invoice_counter
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
<<<<<<< Updated upstream
                        # Mock _increment_invoice_counter to return the next counter value
                        with patch('functions.submit_weekly._increment_invoice_counter', return_value=1):
                            with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                # Mock DynamoDB resource for put_item
                                mock_table = MagicMock()
                                mock_boto_resource.return_value.Table.return_value = mock_table
=======
                        with patch('functions.submit_weekly.put_invoice') as mock_put_invoice:
                            with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                                with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                    # Mock DynamoDB client for TransactWriteItems
                                    mock_dynamodb_client = MagicMock()
                                    mock_boto_client.return_value = mock_dynamodb_client

                                    # Mock DynamoDB resource for put_item
                                    mock_table = MagicMock()
                                    mock_boto_resource.return_value.Table.return_value = mock_table
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
                        with patch('functions.submit_weekly._increment_invoice_counter', return_value=1):
                            with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                mock_table = MagicMock()
                                mock_boto_resource.return_value.Table.return_value = mock_table
=======
                        with patch('functions.submit_weekly.put_invoice') as mock_put_invoice:
                            with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                                with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                    mock_dynamodb_client = MagicMock()
                                    mock_boto_client.return_value = mock_dynamodb_client
                                    mock_table = MagicMock()
                                    mock_boto_resource.return_value.Table.return_value = mock_table
>>>>>>> Stashed changes

                                    response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        # 50 hours × $30 = $1500 subtotal
        # $1500 × 8.25% = $123.75 tax
        # Total = $1623.75
        assert body['totalPay'] == 1623.75

    def test_lambda_response_has_no_cors_headers(self):
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
<<<<<<< Updated upstream
                        # Mock _increment_invoice_counter to return the next counter value
                        with patch('functions.submit_weekly._increment_invoice_counter', return_value=1):
                            with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                # Mock DynamoDB resource for put_item
                                mock_table = MagicMock()
                                mock_boto_resource.return_value.Table.return_value = mock_table
=======
                        with patch('functions.submit_weekly.put_invoice') as mock_put_invoice:
                            with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                                with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                    # Mock DynamoDB client for TransactWriteItems
                                    mock_dynamodb_client = MagicMock()
                                    mock_boto_client.return_value = mock_dynamodb_client

                                    # Mock DynamoDB resource for put_item
                                    mock_table = MagicMock()
                                    mock_boto_resource.return_value.Table.return_value = mock_table
>>>>>>> Stashed changes

                                    response = handler(event, {})

        assert response['statusCode'] == 200
        # Lambda should NOT set CORS headers - API Gateway handles them
        assert 'Access-Control-Allow-Origin' not in response['headers']
        assert 'Access-Control-Allow-Methods' not in response['headers']
        assert 'Access-Control-Allow-Headers' not in response['headers']
        # But Content-Type should still be set
        assert response['headers']['Content-Type'] == 'application/json'

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

    def test_submit_weekly_with_send(self):
        """POST with saveOnly=False should send email and update status to 'sent'"""
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
                'saveOnly': False  # Phase 3: send email
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
                        with patch('functions.submit_weekly.send_weekly_email') as mock_send_email:
                            with patch('functions.submit_weekly.put_invoice') as mock_put_invoice:
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
        assert 'sent' in body
        assert body['sent'] == ['client@example.com', 'accountant@example.com']
        assert body['status'] == 'sent'

        # Verify email was sent with correct parameters
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[1]['to_addresses'] == ['client@example.com', 'accountant@example.com']
        assert call_args[1]['user_name'] == 'Test User'

    def test_submit_weekly_duplicate_invoice(self):
        """POST should handle duplicate invoice ID gracefully"""
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

        # Mock ConditionalCheckFailedException (invoice ID already exists)
        duplicate_error = ClientError(
            {
                'Error': {
                    'Code': 'ConditionalCheckFailedException',
                    'Message': 'The conditional request failed'
                }
            },
            'PutItem'
        )

        with patch.dict(os.environ, {
            'USERS_TABLE': 'users-table',
            'INVOICES_TABLE': 'invoices-table',
            'SST_Resource_InvoiStorage_name': 'test-bucket'
        }):
            with patch('functions.submit_weekly.get_user', return_value=mock_user):
                with patch('functions.submit_weekly.generate_weekly_invoice', return_value=mock_pdf_bytes):
                    with patch('functions.submit_weekly._increment_invoice_counter', return_value=1):
                        with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                            # Mock DynamoDB resource to raise ConditionalCheckFailedException on put_item
                            mock_table = MagicMock()
                            mock_table.put_item.side_effect = duplicate_error
                            mock_boto_resource.return_value.Table.return_value = mock_table

                            response = handler(event, {})

        # Should return 400 error when invoice already exists (client sent duplicate)
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'already exists' in body['error'].lower()

    def test_submit_weekly_email_failure_returns_warning(self):
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
                'saveOnly': False  # Phase 3: send email
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
                        with patch('functions.submit_weekly.send_weekly_email', side_effect=Exception('SES error')):
                            with patch('functions.submit_weekly.put_invoice') as mock_put_invoice:
                                with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                                    with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                        # Mock DynamoDB client for TransactWriteItems
                                        mock_dynamodb_client = MagicMock()
                                        mock_boto_client.return_value = mock_dynamodb_client

                                        # Mock DynamoDB resource for put_item
                                        mock_table = MagicMock()
                                        mock_boto_resource.return_value.Table.return_value = mock_table

                                        response = handler(event, {})

        # Should return 200 with warning, not error
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'emailWarning' in body
        assert 'SES error' in body['emailWarning']
        assert body['sent'] == []
        assert body['status'] == 'draft'  # Status should remain draft since email failed

    def test_populate_hours_from_default_shift(self):
        """Default shift should populate hours correctly"""
        default_shift = {
            'start': '09:00',
            'end': '17:00',
            'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        }

        hours = _populate_hours_from_default_shift(default_shift)

        # Should populate Mon-Fri with 8 hours each (9am to 5pm = 8 hours)
        assert hours['Monday'] == 8.0
        assert hours['Tuesday'] == 8.0
        assert hours['Wednesday'] == 8.0
        assert hours['Thursday'] == 8.0
        assert hours['Friday'] == 8.0
        assert hours['Saturday'] == 0
        assert hours['Sunday'] == 0

    def test_populate_hours_from_default_shift_custom_hours(self):
        """Default shift with custom hours (6am to 2pm = 8 hours)"""
        default_shift = {
            'start': '06:00',
            'end': '14:00',
            'days': ['Mon', 'Tue', 'Wed', 'Thu']
        }

        hours = _populate_hours_from_default_shift(default_shift)

        assert hours['Monday'] == 8.0
        assert hours['Tuesday'] == 8.0
        assert hours['Wednesday'] == 8.0
        assert hours['Thursday'] == 8.0
        assert hours['Friday'] == 0
        assert hours['Saturday'] == 0
        assert hours['Sunday'] == 0

    def test_populate_hours_from_default_shift_fractional_hours(self):
        """Default shift with half hours (9am to 1:30pm = 4.5 hours)"""
        default_shift = {
            'start': '09:00',
            'end': '13:30',
            'days': ['Mon', 'Wed', 'Fri']
        }

        hours = _populate_hours_from_default_shift(default_shift)

        assert hours['Monday'] == 4.5
        assert hours['Tuesday'] == 0
        assert hours['Wednesday'] == 4.5
        assert hours['Thursday'] == 0
        assert hours['Friday'] == 4.5
        assert hours['Saturday'] == 0
        assert hours['Sunday'] == 0

    def test_submit_weekly_with_default_shift_prefill(self):
        """POST with no hours but default shift configured should succeed"""
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
                'hours': {},  # Empty hours - should use default shift
                'week': {
                    'start': '2026-03-24',
                    'end': '2026-03-30',
                    'invNum': 'INV-20260324'
                },
                'saveOnly': True
            })
        }

        # Mock user config with client that has default shift
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
                    'email': 'client@example.com',
                    'defaultShift': {
                        'start': '09:00',
                        'end': '17:00',
                        'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
                    }
                }
            ]
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
                        with patch('functions.submit_weekly.put_invoice') as mock_put_invoice:
                            with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                                with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                    mock_dynamodb_client = MagicMock()
                                    mock_boto_client.return_value = mock_dynamodb_client
                                    mock_table = MagicMock()
                                    mock_boto_resource.return_value.Table.return_value = mock_table

                                    response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        # Default shift is Mon-Fri, 9am-5pm (8 hours each) = 40 hours total
        assert body['totalHours'] == 40.0
        # 40 hours × $28/hr = $1120
        assert body['totalPay'] == 1120.0

    def test_submit_weekly_no_hours_no_default_shift(self):
        """POST with no hours and no default shift should return 400"""
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
                'hours': {},  # Empty hours
                'week': {
                    'start': '2026-03-24',
                    'end': '2026-03-30',
                    'invNum': 'INV-20260324'
                }
            })
        }

        # Mock user config with client that has NO default shift
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'address': '123 Main St',
            'personalEmail': 'test@example.com',
            'rate': 28.00,
            'activeClientId': 'client-1',
            'clients': [
                {
                    'id': 'client-1',
                    'name': 'Test Client',
                    'email': 'client@example.com'
                    # No defaultShift configured
                }
            ]
        }

        with patch('functions.submit_weekly.get_user', return_value=mock_user):
            response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'hours' in body['error'].lower() or 'default shift' in body['error'].lower()

    def test_submit_weekly_metadata_update_failure(self):
        """POST should return 500 if metadata update fails after S3 upload succeeds"""
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

        mock_pdf_bytes = b'%PDF-1.4\nMock PDF content'

        # Mock metadata update failure
        metadata_error = ClientError(
            {
                'Error': {
                    'Code': 'ProvisionedThroughputExceededException',
                    'Message': 'Request rate too high'
                }
            },
            'PutItem'
        )

        with patch.dict(os.environ, {
            'USERS_TABLE': 'users-table',
            'INVOICES_TABLE': 'invoices-table',
            'SST_Resource_InvoiStorage_name': 'test-bucket'
        }):
            with patch('functions.submit_weekly.get_user', return_value=mock_user):
                with patch('functions.submit_weekly.generate_weekly_invoice', return_value=mock_pdf_bytes):
                    with patch('functions.submit_weekly.save_pdf_to_s3'):
                        with patch('functions.submit_weekly.put_invoice') as mock_put_invoice:
                            # Configure put_invoice to raise the metadata error
                            mock_put_invoice.side_effect = metadata_error
                            with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                                with patch('functions.submit_weekly.boto3.resource') as mock_boto_resource:
                                    # Mock DynamoDB client for TransactWriteItems (succeeds)
                                    mock_dynamodb_client = MagicMock()
                                    mock_boto_client.return_value = mock_dynamodb_client

<<<<<<< Updated upstream
                                # Mock DynamoDB resource for put_item
                                # First call (create invoice record) succeeds, second call (metadata update) fails
                                mock_table = MagicMock()
                                mock_table.put_item.side_effect = [None, metadata_error]
                                mock_boto_resource.return_value.Table.return_value = mock_table
=======
                                    # Mock DynamoDB resource (no longer needed for put_item)
                                    mock_table = MagicMock()
                                    mock_boto_resource.return_value.Table.return_value = mock_table
>>>>>>> Stashed changes

                                    response = handler(event, {})

        # Should return 500 error when metadata update fails
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'metadata' in body['error'].lower()
<<<<<<< Updated upstream
        # Should include helpful context about what failed
        assert 'details' in body
        assert 'PDF link' in body['details'] or 'pdfKey' in body.get('details', '')

    def test_increment_invoice_counter_success(self):
        """_increment_invoice_counter should atomically increment and return new value"""
        user_id = 'user-123'

        # Mock DynamoDB client response
        mock_response = {
            'Attributes': {
                'invoiceNumberConfig': {
                    'M': {
                        'nextNum': {'N': '42'}
                    }
                }
            }
        }

        with patch.dict(os.environ, {'USERS_TABLE': 'users-table'}):
            with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                mock_dynamodb = MagicMock()
                mock_dynamodb.update_item.return_value = mock_response
                mock_boto_client.return_value = mock_dynamodb

                result = _increment_invoice_counter(user_id)

        assert result == 42
        mock_dynamodb.update_item.assert_called_once()
        call_args = mock_dynamodb.update_item.call_args[1]
        assert call_args['TableName'] == 'users-table'
        assert call_args['Key'] == {'userId': {'S': user_id}}
        assert 'invoiceNumberConfig.nextNum + :inc' in call_args['UpdateExpression']

    def test_increment_invoice_counter_user_not_found(self):
        """_increment_invoice_counter should raise ValueError when user not found"""
        user_id = 'user-nonexistent'

        # Mock ConditionalCheckFailedException (user doesn't exist or config missing)
        conditional_error = ClientError(
            {
                'Error': {
                    'Code': 'ConditionalCheckFailedException',
                    'Message': 'The conditional request failed'
                }
            },
            'UpdateItem'
        )

        with patch.dict(os.environ, {'USERS_TABLE': 'users-table'}):
            with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                mock_dynamodb = MagicMock()
                mock_dynamodb.update_item.side_effect = conditional_error
                mock_boto_client.return_value = mock_dynamodb

                with pytest.raises(ValueError) as exc_info:
                    _increment_invoice_counter(user_id)

        assert 'invoice counter not initialized' in str(exc_info.value)

    def test_increment_invoice_counter_dynamodb_error(self):
        """_increment_invoice_counter should raise ClientError for other DynamoDB errors"""
        user_id = 'user-123'

        # Mock other DynamoDB error (not ConditionalCheckFailedException)
        throttle_error = ClientError(
            {
                'Error': {
                    'Code': 'ProvisionedThroughputExceededException',
                    'Message': 'Request rate too high'
                }
            },
            'UpdateItem'
        )

        with patch.dict(os.environ, {'USERS_TABLE': 'users-table'}):
            with patch('functions.submit_weekly.boto3.client') as mock_boto_client:
                mock_dynamodb = MagicMock()
                mock_dynamodb.update_item.side_effect = throttle_error
                mock_boto_client.return_value = mock_dynamodb

                with pytest.raises(ClientError) as exc_info:
                    _increment_invoice_counter(user_id)

        assert exc_info.value.response['Error']['Code'] == 'ProvisionedThroughputExceededException'
=======
>>>>>>> Stashed changes
