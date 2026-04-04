import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.pdf import handler
from botocore.exceptions import ClientError


class TestGetPdfUrl:
    """Tests for GET /api/pdf/{id} endpoint"""

    def test_get_pdf_url_returns_signed_url(self):
        """GET /api/pdf/{id} should return signed S3 URL for valid invoice"""
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
            'pdfKey': 'users/user-123/weekly/INV-20260324.pdf'
        }

        mock_signed_url = 'https://s3.amazonaws.com/bucket/users/user-123/weekly/INV-20260324.pdf?signature=xyz'

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.pdf.get_invoice', return_value=mock_invoice):
                with patch('functions.pdf.s3_client.generate_presigned_url', return_value=mock_signed_url):
                    response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['invoiceId'] == 'INV-20260324'
        assert body['pdfUrl'] == mock_signed_url
        assert body['expiresIn'] == 900  # 15 minutes

    def test_get_pdf_url_generates_15_minute_expiration(self):
        """GET /api/pdf/{id} should generate URL with 900 second expiration"""
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
            'pdfKey': 'users/user-123/weekly/INV-20260324.pdf'
        }

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.pdf.get_invoice', return_value=mock_invoice):
                with patch('functions.pdf.s3_client.generate_presigned_url', return_value='https://url') as mock_s3:
                    response = handler(event, {})

        # Verify S3 presigned URL was called with correct expiration
        mock_s3.assert_called_once()
        call_kwargs = mock_s3.call_args
        assert call_kwargs[1]['ExpiresIn'] == 900

    def test_get_pdf_url_uses_correct_bucket_and_key(self):
        """GET /api/pdf/{id} should use correct S3 bucket and key"""
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
            'pdfKey': 'users/user-123/weekly/INV-20260324.pdf'
        }

        with patch.dict(os.environ, {'InvoiStorage': 'invoi-bucket'}):
            with patch('functions.pdf.get_invoice', return_value=mock_invoice):
                with patch('functions.pdf.s3_client.generate_presigned_url', return_value='https://url') as mock_s3:
                    response = handler(event, {})

        # Verify correct bucket and key were used
        call_kwargs = mock_s3.call_args
        assert call_kwargs[1]['Params']['Bucket'] == 'invoi-bucket'
        assert call_kwargs[1]['Params']['Key'] == 'users/user-123/weekly/INV-20260324.pdf'

    def test_get_pdf_url_without_auth_returns_401(self):
        """GET /api/pdf/{id} without Authorization header should return 401"""
        event = {
            'requestContext': {'http': {'method': 'GET'}},
            'headers': {},
            'pathParameters': {'id': 'INV-20260324'}
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'authorization' in body['error'].lower()

    def test_get_pdf_url_with_invalid_jwt_returns_401(self):
        """GET /api/pdf/{id} with invalid JWT (no claims) should return 401"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {}  # No JWT claims
            },
            'headers': {'Authorization': 'Bearer invalid-token'},
            'pathParameters': {'id': 'INV-20260324'}
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body

    def test_get_pdf_url_non_existent_invoice_returns_404(self):
        """GET /api/pdf/{id} for non-existent invoice should return 404"""
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

        # Mock invoice not found
        with patch('functions.pdf.get_invoice', return_value=None):
            response = handler(event, {})

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'not found' in body['error'].lower()

    def test_get_pdf_url_other_users_invoice_returns_403(self):
        """GET /api/pdf/{id} for invoice belonging to another user should return 403"""
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

        # Mock invoice that belongs to a different user
        mock_invoice = {
            'userId': 'user-456',  # Different user
            'invoiceId': 'INV-20260324',
            'pdfKey': 'users/user-456/weekly/INV-20260324.pdf'
        }

        with patch('functions.pdf.get_invoice', return_value=mock_invoice):
            response = handler(event, {})

        assert response['statusCode'] == 403
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'unauthorized' in body['error'].lower()

    def test_get_pdf_url_invoice_without_pdf_returns_404(self):
        """GET /api/pdf/{id} for invoice without pdfKey should return 404"""
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

        # Mock invoice without pdfKey
        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'INV-20260324',
            'status': 'draft'
            # No pdfKey field
        }

        with patch('functions.pdf.get_invoice', return_value=mock_invoice):
            response = handler(event, {})

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'pdf not available' in body['error'].lower()

    def test_get_pdf_url_missing_invoice_id_returns_400(self):
        """GET /api/pdf without invoice ID in path should return 400"""
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
            'pathParameters': {}
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'invoice id' in body['error'].lower()

    def test_get_pdf_url_missing_bucket_config_returns_500(self):
        """GET /api/pdf/{id} without bucket config should return 500"""
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
            'pdfKey': 'users/user-123/weekly/INV-20260324.pdf'
        }

        # Test with missing bucket environment variable
        with patch.dict(os.environ, {}, clear=True):
            with patch('functions.pdf.get_invoice', return_value=mock_invoice):
                response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'storage configuration' in body['error'].lower()

    def test_get_pdf_url_s3_error_returns_500(self):
        """GET /api/pdf/{id} should return 500 when S3 operation fails"""
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
            'pdfKey': 'users/user-123/weekly/INV-20260324.pdf'
        }

        # Mock S3 error
        mock_error = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'The specified key does not exist'}},
            'GeneratePresignedUrl'
        )

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.pdf.get_invoice', return_value=mock_invoice):
                with patch('functions.pdf.s3_client.generate_presigned_url', side_effect=mock_error):
                    response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'failed to generate download url' in body['error'].lower()

    def test_get_pdf_url_dynamodb_error_returns_500(self):
        """GET /api/pdf/{id} should return 500 when DynamoDB operation fails"""
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

        # Mock DynamoDB error
        mock_error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'GetItem'
        )

        with patch('functions.pdf.get_invoice', side_effect=mock_error):
            response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body

    def test_get_pdf_url_handles_monthly_report_pdfs(self):
        """GET /api/pdf/{id} should handle monthly report PDFs"""
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
            'pathParameters': {'id': 'RPT-2026-03'}
        }

        # Mock monthly report invoice
        mock_invoice = {
            'userId': 'user-123',
            'invoiceId': 'RPT-2026-03',
            'pdfKey': 'users/user-123/monthly/RPT-2026-03.pdf',
            'type': 'monthly'
        }

        mock_signed_url = 'https://s3.amazonaws.com/bucket/users/user-123/monthly/RPT-2026-03.pdf?signature=xyz'

        with patch.dict(os.environ, {'InvoiStorage': 'test-bucket'}):
            with patch('functions.pdf.get_invoice', return_value=mock_invoice):
                with patch('functions.pdf.s3_client.generate_presigned_url', return_value=mock_signed_url):
                    response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['invoiceId'] == 'RPT-2026-03'
        assert body['pdfUrl'] == mock_signed_url


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
        assert 'GET' in response['headers']['Access-Control-Allow-Methods']

    def test_all_responses_include_cors_headers(self):
        """All responses should include CORS headers"""
        event = {
            'requestContext': {'http': {'method': 'GET'}},
            'headers': {},  # Missing auth to trigger 401
            'pathParameters': {'id': 'INV-20260324'}
        }

        response = handler(event, {})

        assert 'Access-Control-Allow-Origin' in response['headers']
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
