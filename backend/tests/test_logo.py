"""
Unit tests for logo.py Lambda function

Tests logo upload, retrieval, and deletion functionality.
"""
import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.logo import handler


class TestLogoCORS:
    """
    Test that logo Lambda function does NOT set CORS headers.
    Lambda functions no longer set CORS headers directly.
    API Gateway automatically adds CORS headers based on the configuration.
    """

    def test_lambda_response_has_no_cors_headers_get(self):
        """Lambda GET responses should not include CORS headers (API Gateway handles them)"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'}
        }

        # Mock user with no logo
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User'
        }

        with patch('functions.logo.get_user', return_value=mock_user):
            with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': 'test-bucket'}):
                response = handler(event, {})

        assert response['statusCode'] == 404
        # Lambda should NOT set CORS headers - API Gateway handles them
        assert 'Access-Control-Allow-Origin' not in response['headers']
        assert 'Access-Control-Allow-Methods' not in response['headers']
        assert 'Access-Control-Allow-Headers' not in response['headers']
        # But Content-Type should still be set
        assert response['headers']['Content-Type'] == 'application/json'

    def test_lambda_response_has_no_cors_headers_post(self):
        """Lambda POST responses should not include CORS headers (API Gateway handles them)"""
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
                'imageData': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
                'logoSize': 'medium'
            })
        }

        # Mock user
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User'
        }

        with patch('functions.logo.get_user', return_value=mock_user):
            with patch('functions.logo.get_s3_client') as mock_get_s3:
                mock_s3 = MagicMock()
                mock_get_s3.return_value = mock_s3
                with patch('functions.logo.put_user'):
                    with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': 'test-bucket'}):
                        response = handler(event, {})

        assert response['statusCode'] == 200
        # Lambda should NOT set CORS headers - API Gateway handles them
        assert 'Access-Control-Allow-Origin' not in response['headers']
        assert 'Access-Control-Allow-Methods' not in response['headers']
        assert 'Access-Control-Allow-Headers' not in response['headers']
        # But Content-Type should still be set
        assert response['headers']['Content-Type'] == 'application/json'

    def test_lambda_response_has_no_cors_headers_delete(self):
        """Lambda DELETE responses should not include CORS headers (API Gateway handles them)"""
        event = {
            'requestContext': {
                'http': {'method': 'DELETE'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'}
        }

        # Mock user with logo
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'logoKey': 'users/user-123/logo.png'
        }

        with patch('functions.logo.get_user', return_value=mock_user):
            with patch('functions.logo.get_s3_client') as mock_get_s3:
                mock_s3 = MagicMock()
                mock_get_s3.return_value = mock_s3
                with patch('functions.logo.put_user'):
                    with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': 'test-bucket'}):
                        response = handler(event, {})

        assert response['statusCode'] == 200
        # Lambda should NOT set CORS headers - API Gateway handles them
        assert 'Access-Control-Allow-Origin' not in response['headers']
        assert 'Access-Control-Allow-Methods' not in response['headers']
        assert 'Access-Control-Allow-Headers' not in response['headers']
        # But Content-Type should still be set
        assert response['headers']['Content-Type'] == 'application/json'
