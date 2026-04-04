import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.export import handler
from botocore.exceptions import ClientError


class TestCsvExport:
    """Tests for CSV export functionality"""

    def test_csv_export_returns_signed_url(self):
        """POST /api/export with format=csv should return signed S3 URL"""
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
                'invoiceIds': ['INV-001', 'INV-002'],
                'format': 'csv'
            })
        }

        mock_invoice_1 = {
            'userId': 'user-123',
            'invoiceId': 'INV-001',
            'weekStart': '2026-03-24',
            'clientId': 'client-abc',
            'totalHours': 40,
            'totalPay': Decimal('1120.00'),
            'status': 'paid'
        }

        mock_invoice_2 = {
            'userId': 'user-123',
            'invoiceId': 'INV-002',
            'weekStart': '2026-03-31',
            'clientId': 'client-abc',
            'totalHours': 35,
            'totalPay': Decimal('980.00'),
            'status': 'sent'
        }

        mock_signed_url = 'https://s3.amazonaws.com/bucket/users/user-123/exports/export-20260404-120000.csv?signature=xyz'

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.export.get_invoice', side_effect=[mock_invoice_1, mock_invoice_2]):
                with patch('functions.export.s3_client.put_object') as mock_put:
                    with patch('functions.export.s3_client.generate_presigned_url', return_value=mock_signed_url):
                        response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['format'] == 'csv'
        assert body['downloadUrl'] == mock_signed_url
        assert body['expiresIn'] == 3600
        assert body['invoiceCount'] == 2

    def test_csv_export_uploads_with_correct_content_type(self):
        """CSV export should upload to S3 with text/csv content type"""
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
                'invoiceIds': ['INV-001'],
                'format': 'csv'
            })
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-001',
            'weekStart': '2026-03-24',
            'clientId': 'client-abc',
            'totalHours': 40,
            'totalPay': 1120.00,
            'status': 'paid'
        }

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.export.get_invoice', return_value=mock_invoice):
                with patch('functions.export.s3_client.put_object') as mock_put:
                    with patch('functions.export.s3_client.generate_presigned_url', return_value='https://url'):
                        response = handler(event, {})

        # Verify S3 upload was called with correct content type
        mock_put.assert_called_once()
        call_kwargs = mock_put.call_args[1]
        assert call_kwargs['ContentType'] == 'text/csv'
        assert 'invoices-' in call_kwargs['ContentDisposition']
        assert '.csv' in call_kwargs['ContentDisposition']

    def test_csv_export_contains_correct_columns(self):
        """CSV export should contain headers and data in correct format"""
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
                'invoiceIds': ['INV-001'],
                'format': 'csv'
            })
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-001',
            'weekStart': '2026-03-24',
            'clientId': 'client-abc',
            'totalHours': 40,
            'totalPay': Decimal('1120.00'),
            'status': 'paid'
        }

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.export.get_invoice', return_value=mock_invoice):
                with patch('functions.export.s3_client.put_object') as mock_put:
                    with patch('functions.export.s3_client.generate_presigned_url', return_value='https://url'):
                        response = handler(event, {})

        # Verify CSV content
        csv_content = mock_put.call_args[1]['Body'].decode('utf-8')
        lines = csv_content.strip().split('\n')

        # Check header
        assert 'Invoice ID,Date,Client,Hours,Amount,Status' in lines[0]

        # Check data row
        assert 'INV-001' in lines[1]
        assert '2026-03-24' in lines[1]
        assert 'client-abc' in lines[1]
        assert '40' in lines[1]
        assert '1120.00' in lines[1]
        assert 'paid' in lines[1]


class TestZipExport:
    """Tests for ZIP export functionality"""

    def test_zip_export_returns_signed_url(self):
        """POST /api/export with format=zip should return signed S3 URL"""
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
                'invoiceIds': ['INV-001'],
                'format': 'zip'
            })
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-001',
            'pdfKey': 'users/user-123/weekly/INV-001.pdf'
        }

        mock_pdf_data = b'%PDF-1.4 mock pdf content'
        mock_signed_url = 'https://s3.amazonaws.com/bucket/users/user-123/exports/export-20260404-120000.zip?signature=xyz'

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.export.get_invoice', return_value=mock_invoice):
                with patch('functions.export.s3_client.get_object', return_value={'Body': MagicMock(read=lambda: mock_pdf_data)}):
                    with patch('functions.export.s3_client.put_object'):
                        with patch('functions.export.s3_client.generate_presigned_url', return_value=mock_signed_url):
                            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['format'] == 'zip'
        assert body['downloadUrl'] == mock_signed_url
        assert body['expiresIn'] == 3600
        assert body['invoiceCount'] == 1
        assert body['pdfCount'] == 1

    def test_zip_export_includes_log_pdfs(self):
        """ZIP export should include log PDFs when available"""
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
                'invoiceIds': ['INV-001'],
                'format': 'zip'
            })
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-001',
            'pdfKey': 'users/user-123/weekly/INV-001.pdf',
            'logPdfKey': 'users/user-123/logs/LOG-001.pdf'
        }

        mock_pdf_data = b'%PDF-1.4 mock pdf'
        mock_log_data = b'%PDF-1.4 mock log pdf'

        def mock_get_object(Bucket, Key):
            if 'log' in Key.lower():
                return {'Body': MagicMock(read=lambda: mock_log_data)}
            return {'Body': MagicMock(read=lambda: mock_pdf_data)}

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.export.get_invoice', return_value=mock_invoice):
                with patch('functions.export.s3_client.get_object', side_effect=mock_get_object):
                    with patch('functions.export.s3_client.put_object'):
                        with patch('functions.export.s3_client.generate_presigned_url', return_value='https://url'):
                            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['pdfCount'] == 2  # Invoice PDF + Log PDF

    def test_zip_export_no_pdfs_returns_404(self):
        """ZIP export should return 404 when no PDFs are available"""
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
                'invoiceIds': ['INV-001'],
                'format': 'zip'
            })
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-001',
            # No pdfKey or logPdfKey
        }

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.export.get_invoice', return_value=mock_invoice):
                response = handler(event, {})

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'no pdfs available' in body['error'].lower()

    def test_zip_export_uploads_with_correct_content_type(self):
        """ZIP export should upload to S3 with application/zip content type"""
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
                'invoiceIds': ['INV-001'],
                'format': 'zip'
            })
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-001',
            'pdfKey': 'users/user-123/weekly/INV-001.pdf'
        }

        mock_pdf_data = b'%PDF-1.4 mock pdf'

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.export.get_invoice', return_value=mock_invoice):
                with patch('functions.export.s3_client.get_object', return_value={'Body': MagicMock(read=lambda: mock_pdf_data)}):
                    with patch('functions.export.s3_client.put_object') as mock_put:
                        with patch('functions.export.s3_client.generate_presigned_url', return_value='https://url'):
                            response = handler(event, {})

        # Verify S3 upload was called with correct content type
        mock_put.assert_called_once()
        call_kwargs = mock_put.call_args[1]
        assert call_kwargs['ContentType'] == 'application/zip'
        assert 'invoices-' in call_kwargs['ContentDisposition']
        assert '.zip' in call_kwargs['ContentDisposition']


class TestAuthAndValidation:
    """Tests for authentication and request validation"""

    def test_export_without_auth_returns_401(self):
        """POST /api/export without Authorization header should return 401"""
        event = {
            'requestContext': {'http': {'method': 'POST'}},
            'headers': {},
            'body': json.dumps({
                'invoiceIds': ['INV-001'],
                'format': 'csv'
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'authorization' in body['error'].lower()

    def test_export_with_invalid_jwt_returns_401(self):
        """POST /api/export with invalid JWT should return 401"""
        event = {
            'requestContext': {
                'http': {'method': 'POST'},
                'authorizer': {}  # No JWT claims
            },
            'headers': {'Authorization': 'Bearer invalid-token'},
            'body': json.dumps({
                'invoiceIds': ['INV-001'],
                'format': 'csv'
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body

    def test_export_without_invoice_ids_returns_400(self):
        """POST /api/export without invoiceIds should return 400"""
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
                'format': 'csv'
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'invoiceids' in body['error'].lower()

    def test_export_with_empty_invoice_ids_returns_400(self):
        """POST /api/export with empty invoiceIds array should return 400"""
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
                'invoiceIds': [],
                'format': 'csv'
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'invoiceids' in body['error'].lower()

    def test_export_with_invalid_format_returns_400(self):
        """POST /api/export with invalid format should return 400"""
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
                'invoiceIds': ['INV-001'],
                'format': 'pdf'  # Invalid format
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'format' in body['error'].lower()

    def test_export_with_invalid_json_returns_400(self):
        """POST /api/export with invalid JSON should return 400"""
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
            'body': 'invalid json {'
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'json' in body['error'].lower()

    def test_export_non_existent_invoice_returns_404(self):
        """POST /api/export for non-existent invoice should return 404"""
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
                'invoiceIds': ['INV-99999'],
                'format': 'csv'
            })
        }

        with patch('functions.export.get_invoice', return_value=None):
            response = handler(event, {})

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'not found' in body['error'].lower()

    def test_export_other_users_invoice_returns_404(self):
        """POST /api/export for invoice belonging to another user should return 404"""
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
                'invoiceIds': ['INV-001'],
                'format': 'csv'
            })
        }

        mock_invoice = {
            'userId': 'user-456',  # Different user
            'invoiceId': 'INV-001',
            'pdfKey': 'users/user-456/weekly/INV-001.pdf'
        }

        with patch('functions.export.get_invoice', return_value=mock_invoice):
            response = handler(event, {})

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'not found' in body['error'].lower() or 'access denied' in body['error'].lower()


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
        assert 'POST' in response['headers']['Access-Control-Allow-Methods']

    def test_all_responses_include_cors_headers(self):
        """All responses should include CORS headers"""
        event = {
            'requestContext': {'http': {'method': 'POST'}},
            'headers': {},  # Missing auth to trigger 401
            'body': json.dumps({
                'invoiceIds': ['INV-001'],
                'format': 'csv'
            })
        }

        response = handler(event, {})

        assert 'Access-Control-Allow-Origin' in response['headers']
        assert response['headers']['Access-Control-Allow-Origin'] == '*'


class TestErrorHandling:
    """Tests for error handling"""

    def test_export_s3_error_returns_500(self):
        """Export should return 500 when S3 operation fails"""
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
                'invoiceIds': ['INV-001'],
                'format': 'csv'
            })
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-001',
            'weekStart': '2026-03-24',
            'totalHours': 40,
            'totalPay': 1120.00,
            'status': 'paid'
        }

        mock_error = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'PutObject'
        )

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.export.get_invoice', return_value=mock_invoice):
                with patch('functions.export.s3_client.put_object', side_effect=mock_error):
                    response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body

    def test_export_missing_bucket_config_returns_500(self):
        """Export should return 500 when bucket config is missing"""
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
                'invoiceIds': ['INV-001'],
                'format': 'csv'
            })
        }

        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-001'
        }

        with patch.dict(os.environ, {}, clear=True):
            with patch('functions.export.get_invoice', return_value=mock_invoice):
                response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'storage configuration' in body['error'].lower()
