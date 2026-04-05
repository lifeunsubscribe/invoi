import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from functions.scan_month import handler
from botocore.exceptions import ClientError


class TestScanMonth:
    """Tests for GET /api/scan-month endpoint"""

    def test_scan_month_with_invoices_returns_array(self):
        """GET with valid params should return array of invoices for the month"""
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
                'year': '2026',
                'month': '3'
            }
        }

        # Mock invoices for March 2026
        mock_invoices = [
            {
                'userId': 'user-123',
                'invoiceId': 'INV-20260303',
                'type': 'weekly',
                'totalHours': 40,
                'totalPay': 1120.00
            },
            {
                'userId': 'user-123',
                'invoiceId': 'INV-20260310',
                'type': 'weekly',
                'totalHours': 38,
                'totalPay': 1064.00
            }
        ]

        with patch('functions.scan_month.query_invoices', return_value=mock_invoices):
            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert isinstance(body, list)
        assert len(body) == 2
        assert body[0]['invoiceId'] == 'INV-20260303'
        assert body[1]['invoiceId'] == 'INV-20260310'

    def test_scan_month_empty_month_returns_empty_array(self):
        """GET for month with no invoices should return empty array (not error)"""
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
                'year': '2026',
                'month': '12'
            }
        }

        with patch('functions.scan_month.query_invoices', return_value=[]):
            response = handler(event, {})

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert isinstance(body, list)
        assert len(body) == 0

    def test_scan_month_queries_correct_date_range(self):
        """Should construct correct invoiceId range for DynamoDB query"""
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
                'year': '2026',
                'month': '3'
            }
        }

        with patch('functions.scan_month.query_invoices', return_value=[]) as mock_query:
            handler(event, {})

            # Verify query_invoices was called with correct parameters
            mock_query.assert_called_once()
            call_args = mock_query.call_args
            assert call_args[0][0] == 'user-123'  # userId
            assert call_args[1]['filters']['invoiceId_start'] == 'INV-20260301'
            assert call_args[1]['filters']['invoiceId_end'] == 'INV-20260331'
            assert call_args[1]['filters']['type'] == 'weekly'

    def test_scan_month_filters_weekly_invoices_only(self):
        """Should filter for type=weekly to exclude monthly reports"""
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
                'year': '2026',
                'month': '3'
            }
        }

        with patch('functions.scan_month.query_invoices', return_value=[]) as mock_query:
            handler(event, {})

            # Verify type filter is set to weekly
            filters = mock_query.call_args[1]['filters']
            assert filters['type'] == 'weekly'

    def test_scan_month_missing_year_returns_400(self):
        """GET without year parameter should return 400"""
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
                'month': '3'
            }
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'year and month' in body['error'].lower()

    def test_scan_month_missing_month_returns_400(self):
        """GET without month parameter should return 400"""
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
                'year': '2026'
            }
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_scan_month_invalid_month_returns_400(self):
        """GET with month outside 1-12 range should return 400"""
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
                'year': '2026',
                'month': '13'
            }
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'month' in body['error'].lower()

    def test_scan_month_month_zero_returns_400(self):
        """GET with month=0 should return 400"""
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
                'year': '2026',
                'month': '0'
            }
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_scan_month_invalid_year_returns_400(self):
        """GET with year outside valid range should return 400"""
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
                'year': '1800',
                'month': '3'
            }
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'year' in body['error'].lower()

    def test_scan_month_non_numeric_year_returns_400(self):
        """GET with non-numeric year should return 400"""
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
                'year': 'abc',
                'month': '3'
            }
        }

        response = handler(event, {})

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'integer' in body['error'].lower()

    def test_scan_month_without_auth_returns_401(self):
        """GET without Authorization header should return 401"""
        event = {
            'requestContext': {'http': {'method': 'GET'}},
            'headers': {},
            'queryStringParameters': {
                'year': '2026',
                'month': '3'
            }
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Missing Authorization header' in body['error']

    def test_scan_month_with_invalid_jwt_returns_401(self):
        """GET with invalid JWT (no claims) should return 401"""
        event = {
            'requestContext': {
                'http': {'method': 'GET'},
                'authorizer': {}  # No JWT claims
            },
            'headers': {'Authorization': 'Bearer invalid-token'},
            'queryStringParameters': {
                'year': '2026',
                'month': '3'
            }
        }

        response = handler(event, {})

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body

    def test_scan_month_handles_dynamodb_error(self):
        """Should return 500 when DynamoDB operation fails"""
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
                'year': '2026',
                'month': '3'
            }
        }

        # Mock DynamoDB error
        mock_error = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'Query'
        )

        with patch('functions.scan_month.query_invoices', side_effect=mock_error):
            response = handler(event, {})

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body

    def test_scan_month_february_uses_day_31(self):
        """February query should use day 31 (safe to query non-existent dates)"""
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
                'year': '2026',
                'month': '2'
            }
        }

        with patch('functions.scan_month.query_invoices', return_value=[]) as mock_query:
            handler(event, {})

            # Verify range includes day 31 (catches all dates, safe for DynamoDB BETWEEN)
            filters = mock_query.call_args[1]['filters']
            assert filters['invoiceId_start'] == 'INV-20260201'
            assert filters['invoiceId_end'] == 'INV-20260231'

    def test_scan_month_single_digit_month_zero_padded(self):
        """Single-digit months should be zero-padded in invoiceId range"""
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
                'year': '2026',
                'month': '5'
            }
        }

        with patch('functions.scan_month.query_invoices', return_value=[]) as mock_query:
            handler(event, {})

            filters = mock_query.call_args[1]['filters']
            assert filters['invoiceId_start'] == 'INV-20260501'
            assert filters['invoiceId_end'] == 'INV-20260531'


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
            'queryStringParameters': {
                'year': '2026',
                'month': '3'
            }
        }

        mock_invoices = [
            {'userId': 'user-123', 'invoiceId': 'INV-20260324', 'status': 'sent'},
        ]

        with patch('functions.scan_month.query_invoices', return_value=mock_invoices):
            response = handler(event, {})

        assert response['statusCode'] == 200
        # Lambda should NOT set CORS headers - API Gateway handles them
        assert 'Access-Control-Allow-Origin' not in response['headers']
        assert 'Access-Control-Allow-Methods' not in response['headers']
        assert 'Access-Control-Allow-Headers' not in response['headers']
        # But Content-Type should still be set
        assert response['headers']['Content-Type'] == 'application/json'
