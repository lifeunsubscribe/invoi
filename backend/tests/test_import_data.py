"""
Unit tests for import_data.py Lambda function

Tests historical invoice import functionality.
"""
import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.import_data import handler


class TestImportDataCORS:
    """
    Test that import_data Lambda function does NOT set CORS headers.
    Lambda functions no longer set CORS headers directly.
    API Gateway automatically adds CORS headers based on the configuration.
    """

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
            'headers': {
                'Authorization': 'Bearer valid-token',
                'content-type': 'multipart/form-data; boundary=----WebKitFormBoundary123'
            },
            'body': '------WebKitFormBoundary123\r\nContent-Disposition: form-data; name="jsons"; filename="invoice-001.json"\r\nContent-Type: application/json\r\n\r\n{"invoiceNumber":"INV-001","date":"2026-03-24","amount":1120}\r\n------WebKitFormBoundary123\r\nContent-Disposition: form-data; name="pdfs"; filename="invoice-001.pdf"\r\nContent-Type: application/pdf\r\n\r\n%PDF-1.4\nfake content\r\n------WebKitFormBoundary123--\r\n'
        }

        # Mock user
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User'
        }

        with patch('functions.import_data.get_user', return_value=mock_user):
            with patch('functions.import_data.s3_client'):
                with patch('functions.import_data.put_invoice'):
                    with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': 'test-bucket'}):
                        response = handler(event, {})

        assert response['statusCode'] == 200
        # Lambda should NOT set CORS headers - API Gateway handles them
        assert 'Access-Control-Allow-Origin' not in response['headers']
        assert 'Access-Control-Allow-Methods' not in response['headers']
        assert 'Access-Control-Allow-Headers' not in response['headers']
        # But Content-Type should still be set
        assert response['headers']['Content-Type'] == 'application/json'
