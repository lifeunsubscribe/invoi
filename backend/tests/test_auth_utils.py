import sys
import os
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.auth_utils import extract_user_id_from_token


class TestExtractUserIdFromToken:
    """Tests for extract_user_id_from_token utility function"""

    def test_extract_from_cognito_jwt_v2(self):
        """Should extract userId from Cognito JWT authorizer (API Gateway v2)"""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {'sub': 'user-123'}
                    }
                }
            }
        }

        user_id = extract_user_id_from_token(event)
        assert user_id == 'user-123'

    def test_extract_from_lambda_authorizer_v1(self):
        """Should extract userId from Lambda authorizer (API Gateway v1)"""
        event = {
            'requestContext': {
                'authorizer': {
                    'claims': {'sub': 'user-456'}
                }
            }
        }

        user_id = extract_user_id_from_token(event)
        assert user_id == 'user-456'

    def test_missing_claims_returns_none(self):
        """Should return None when no valid claims are present"""
        event = {
            'requestContext': {
                'authorizer': {}
            }
        }

        user_id = extract_user_id_from_token(event)
        assert user_id is None

    def test_empty_event_returns_none(self):
        """Should return None for empty event"""
        event = {}

        user_id = extract_user_id_from_token(event)
        assert user_id is None

    def test_malformed_event_returns_none(self):
        """Should handle malformed event gracefully"""
        event = {
            'requestContext': None
        }

        user_id = extract_user_id_from_token(event)
        assert user_id is None
