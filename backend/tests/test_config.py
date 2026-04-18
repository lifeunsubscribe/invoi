import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.config import handler, get_default_profile, validate_profile_fields
from botocore.exceptions import ClientError


class TestGetConfig:
    """Tests for GET /api/config endpoint"""

    def test_get_existing_user_returns_profile(self):
        """GET with valid JWT and existing user should return user profile"""
        # Mock event with valid Cognito JWT claims
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

        # Mock existing user data
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0
        }

        with patch('functions.config.get_user', return_value=mock_user):
            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['userId'] == 'user-123'
        assert body['name'] == 'Test User'
        assert body['email'] == 'test@example.com'

    def test_get_new_user_returns_default_profile(self):
        """GET with valid JWT and new user should return default profile"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'new-user-456'}
                    }
                }
            },
            'headers': {'Authorization': 'Bearer valid-token'}
        }

        # Mock user not found in DB
        with patch('functions.config.get_user', return_value=None):
            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['userId'] == 'new-user-456'
        assert body['name'] == ''
        assert body['email'] == ''
        assert body['rate'] == 0
        assert body['template'] == 'morning-light'
        assert body['clients'] == []

    def test_get_without_auth_header_returns_401(self):
        """GET without Authorization header should return 401"""
        event = {
            'requestContext': {'http': {'method': 'GET'}},
            'headers': {}
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Missing Authorization header' in body['error']

    def test_get_with_invalid_jwt_returns_401(self):
        """GET with invalid JWT (no claims) should return 401"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {}  # No JWT claims
            },
            'headers': {'Authorization': 'Bearer invalid-token'}
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body

    def test_get_handles_dynamodb_error(self):
        """GET should return 500 when DynamoDB operation fails"""
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

        # Mock DynamoDB error
        mock_error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'GetItem'
        )

        with patch('functions.config.get_user', side_effect=mock_error):
            response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body


class TestPostConfig:
    """Tests for POST /api/config endpoint"""

    def test_post_valid_profile_updates_user(self):
        """POST with valid profile data should update user in DB"""
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
                'name': 'Updated User',
                'email': 'updated@example.com',
                'rate': 30.0,
                'address': '123 Main St'
            })
        }

        mock_updated = {
            'userId': 'user-123',
            'name': 'Updated User',
            'email': 'updated@example.com',
            'rate': 30.0,
            'address': '123 Main St'
        }

        with patch('functions.config.put_user', return_value=mock_updated):
            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['name'] == 'Updated User'
        assert body['rate'] == 30.0

    def test_post_missing_required_fields_returns_400(self):
        """POST without required fields should return 400"""
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
                'address': '123 Main St'
                # Missing name, email, rate
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_post_invalid_email_returns_400(self):
        """POST with invalid email format should return 400"""
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
                'name': 'Test User',
                'email': 'not-an-email',
                'rate': 25.0
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'email' in body['error'].lower()

    def test_post_without_auth_returns_401(self):
        """POST without Authorization header should return 401"""
        event = {
            'requestContext': {'http': {'method': 'POST'}},
            'headers': {},
            'body': json.dumps({
                'name': 'Test',
                'email': 'test@example.com',
                'rate': 25.0
            })
        }

        response = handler(event, {})

        assert response['statusCode'] == 401


class TestDefaultProfile:
    """Tests for default profile generation"""

    def test_default_profile_structure(self):
        """get_default_profile should return complete profile structure"""
        profile = get_default_profile('test-user-id')

        # Check required fields
        assert profile['userId'] == 'test-user-id'
        assert profile['email'] == ''
        assert profile['name'] == ''
        assert profile['rate'] == 0
        assert profile['template'] == 'morning-light'
        assert profile['accent'] == '#b76e79'

        # Check invoice number config defaults
        assert profile['invoiceNumberConfig']['prefix'] == 'INV'
        assert profile['invoiceNumberConfig']['includeYear'] is False
        assert profile['invoiceNumberConfig']['padding'] == 3
        assert profile['invoiceNumberConfig']['nextNum'] == 1

        # Check payment/tax defaults
        assert profile['paymentTerms'] == 'receipt'
        assert profile['taxEnabled'] is False
        assert profile['taxRate'] == 0

        # Check collections
        assert profile['clients'] == []
        assert profile['activeClientId'] == ''


class TestValidation:
    """Tests for profile field validation"""

    def test_validate_missing_name(self):
        """Validation should fail when name is missing"""
        data = {'email': 'test@example.com', 'rate': 25.0}
        error = validate_profile_fields(data)
        assert error is not None
        assert 'name' in error.lower()

    def test_validate_missing_email(self):
        """Validation should fail when email is missing"""
        data = {'name': 'Test User', 'rate': 25.0}
        error = validate_profile_fields(data)
        assert error is not None
        assert 'email' in error.lower()

    def test_validate_missing_rate(self):
        """Validation should fail when rate is missing"""
        data = {'name': 'Test User', 'email': 'test@example.com'}
        error = validate_profile_fields(data)
        assert error is not None
        assert 'rate' in error.lower()

    def test_validate_invalid_email_format(self):
        """Validation should fail for invalid email format"""
        data = {'name': 'Test User', 'email': 'invalid-email', 'rate': 25.0}
        error = validate_profile_fields(data)
        assert error is not None
        assert 'email' in error.lower()

    def test_validate_negative_rate(self):
        """Validation should fail for negative rate"""
        data = {'name': 'Test User', 'email': 'test@example.com', 'rate': -10}
        error = validate_profile_fields(data)
        assert error is not None
        assert 'positive' in error.lower()

    def test_validate_zero_rate(self):
        """Validation should fail for zero rate"""
        data = {'name': 'Test User', 'email': 'test@example.com', 'rate': 0}
        error = validate_profile_fields(data)
        assert error is not None
        assert 'positive' in error.lower()

    def test_validate_valid_profile(self):
        """Validation should pass for valid profile data"""
        data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0
        }
        error = validate_profile_fields(data)
        assert error is None

    def test_validate_name_too_long(self):
        """Validation should fail when name exceeds 200 characters"""
        data = {
            'name': 'A' * 201,  # 201 characters
            'email': 'test@example.com',
            'rate': 25.0
        }
        error = validate_profile_fields(data)
        assert error is not None
        assert 'Name cannot exceed 200 characters' in error

    def test_validate_name_at_max_length(self):
        """Validation should pass when name is exactly 200 characters"""
        data = {
            'name': 'A' * 200,  # Exactly 200 characters
            'email': 'test@example.com',
            'rate': 25.0
        }
        error = validate_profile_fields(data)
        assert error is None

    def test_validate_email_too_long(self):
        """Validation should fail when email exceeds 254 characters"""
        # Create email with 255 characters
        # '@example.com' is 12 chars, so need 243 chars to get 255 total
        local_part = 'a' * 243
        email = f'{local_part}@example.com'  # 255 total chars
        data = {
            'name': 'Test User',
            'email': email,
            'rate': 25.0
        }
        error = validate_profile_fields(data)
        assert error is not None
        assert 'Email cannot exceed 254 characters' in error

    def test_validate_email_at_max_length(self):
        """Validation should pass when email is exactly 254 characters"""
        # Create email with 254 characters
        # '@example.com' is 12 chars, so need 242 chars to get 254 total
        local_part = 'a' * 242
        email = f'{local_part}@example.com'  # 254 total chars
        data = {
            'name': 'Test User',
            'email': email,
            'rate': 25.0
        }
        error = validate_profile_fields(data)
        assert error is None

    def test_validate_optional_email_field_too_long(self):
        """Validation should fail when optional email fields exceed 254 characters"""
        data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0,
            'personalEmail': 'a' * 255 + '@example.com'
        }
        error = validate_profile_fields(data)
        assert error is not None
        assert 'personalEmail cannot exceed 254 characters' in error

    def test_validate_optional_email_field_invalid_format(self):
        """Validation should fail when optional email fields have invalid format"""
        invalid_emails = [
            ('personalEmail', 'not-an-email'),
            ('accountantEmail', 'missing@domain'),
            ('clientEmail', '@nodomain.com'),
            ('personalEmail', 'no-at-sign.com'),
        ]
        for field, invalid_email in invalid_emails:
            data = {
                'name': 'Test User',
                'email': 'test@example.com',
                'rate': 25.0,
                field: invalid_email
            }
            error = validate_profile_fields(data)
            assert error is not None
            assert field in error
            assert 'valid email address' in error

    def test_validate_client_name_too_long(self):
        """Validation should fail when clientName exceeds 200 characters"""
        data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0,
            'clientName': 'B' * 201
        }
        error = validate_profile_fields(data)
        assert error is not None
        assert 'clientName cannot exceed 200 characters' in error

    def test_validate_short_text_field_too_long(self):
        """Validation should fail when short text fields exceed 500 characters"""
        data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0,
            'address': 'X' * 501
        }
        error = validate_profile_fields(data)
        assert error is not None
        assert 'address cannot exceed 500 characters' in error

    def test_validate_short_text_field_at_max_length(self):
        """Validation should pass when short text field is exactly 500 characters"""
        data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0,
            'address': 'X' * 500
        }
        error = validate_profile_fields(data)
        assert error is None

    def test_validate_invoice_note_too_long(self):
        """Validation should fail when invoiceNote exceeds 2000 characters"""
        data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0,
            'invoiceNote': 'N' * 2001
        }
        error = validate_profile_fields(data)
        assert error is not None
        assert 'invoiceNote cannot exceed 2000 characters' in error

    def test_validate_invoice_note_at_max_length(self):
        """Validation should pass when invoiceNote is exactly 2000 characters"""
        data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0,
            'invoiceNote': 'N' * 2000
        }
        error = validate_profile_fields(data)
        assert error is None

    def test_validate_id_field_too_long(self):
        """Validation should fail when ID fields exceed 100 characters"""
        data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0,
            'activeClientId': 'I' * 101
        }
        error = validate_profile_fields(data)
        assert error is not None
        assert 'activeClientId cannot exceed 100 characters' in error

    def test_validate_multiple_optional_fields_within_limits(self):
        """Validation should pass when multiple optional fields are within limits"""
        data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0,
            'address': 'X' * 500,
            'invoiceNote': 'N' * 2000,
            'clientName': 'C' * 200,
            'personalEmail': 'a' * 240 + '@example.com'
        }
        error = validate_profile_fields(data)
        assert error is None


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
            'headers': {'Authorization': 'Bearer valid-token'}
        }

        # Mock existing user data
        mock_user = {
            'userId': 'user-123',
            'name': 'Test User',
            'email': 'test@example.com',
            'rate': 25.0
        }

        with patch('functions.config.get_user', return_value=mock_user):
            response = handler(event, {})

        assert response['statusCode'] == 200
        # Lambda should NOT set CORS headers - API Gateway handles them
        assert 'Access-Control-Allow-Origin' not in response['headers']
        assert 'Access-Control-Allow-Methods' not in response['headers']
        assert 'Access-Control-Allow-Headers' not in response['headers']
        # But Content-Type should still be set
        assert response['headers']['Content-Type'] == 'application/json'
