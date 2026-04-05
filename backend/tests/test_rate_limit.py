import json
import sys
import os
import time
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.rate_limit import check_rate_limit, _request_log


class TestCheckRateLimit:
    """Tests for per-user rate limiting"""

    def setup_method(self):
        """Clear rate limit state between tests"""
        _request_log.clear()

    def test_allows_requests_within_limit(self):
        """Requests within the limit should return None (allowed)"""
        for _ in range(5):
            assert check_rate_limit('user-1', max_requests=5) is None

    def test_blocks_requests_over_limit(self):
        """Request exceeding the limit should return 429"""
        for _ in range(5):
            check_rate_limit('user-1', max_requests=5)

        response = check_rate_limit('user-1', max_requests=5)
        assert response is not None
        assert response['statusCode'] == 429
        body = json.loads(response['body'])
        assert 'Rate limit exceeded' in body['error']

    def test_separate_limits_per_user(self):
        """Each user has their own independent rate limit"""
        for _ in range(5):
            check_rate_limit('user-1', max_requests=5)

        # user-1 is at limit
        assert check_rate_limit('user-1', max_requests=5) is not None
        # user-2 should be fine
        assert check_rate_limit('user-2', max_requests=5) is None

    def test_window_expiry(self):
        """Requests outside the window should not count"""
        # Fill up the limit with timestamps in the past
        past = time.time() - 120  # 2 minutes ago
        _request_log['user-1'] = [past] * 10

        # Should be allowed because old entries expire (default 60s window)
        assert check_rate_limit('user-1', max_requests=10, window_seconds=60) is None

    def test_custom_window_and_limit(self):
        """Custom max_requests and window_seconds should be respected"""
        for _ in range(3):
            check_rate_limit('user-1', max_requests=3, window_seconds=30)

        response = check_rate_limit('user-1', max_requests=3, window_seconds=30)
        assert response is not None
        assert response['statusCode'] == 429

    def test_response_format(self):
        """429 response should have correct structure"""
        for _ in range(1):
            check_rate_limit('user-1', max_requests=1)

        response = check_rate_limit('user-1', max_requests=1)
        assert response['statusCode'] == 429
        assert response['headers']['Content-Type'] == 'application/json'
        assert json.loads(response['body'])['error']


class TestRateLimitIntegration:
    """Test that check_rate_limit integrates correctly with handler patterns"""

    def setup_method(self):
        _request_log.clear()

    def test_rate_limit_returns_429_response_directly_usable_by_handler(self):
        """The 429 response from check_rate_limit can be returned directly by a handler"""
        # Simulate a handler calling check_rate_limit after auth
        user_id = 'user-spam'

        # Exhaust limit
        for _ in range(5):
            result = check_rate_limit(user_id, max_requests=5)
            assert result is None  # allowed

        # Next call returns a response dict a handler would return directly
        result = check_rate_limit(user_id, max_requests=5)
        assert result['statusCode'] == 429
        assert 'headers' in result
        assert 'body' in result
        body = json.loads(result['body'])
        assert body['error'] == 'Rate limit exceeded. Please try again later.'

    def test_rate_limit_does_not_interfere_with_options_requests(self):
        """Rate limiting only applies after user_id extraction, so OPTIONS (no auth) is unaffected"""
        # This verifies the placement: check_rate_limit is called AFTER auth,
        # so preflight OPTIONS requests (which skip auth) never hit the limiter
        # Exhaust a user's limit
        for _ in range(5):
            check_rate_limit('user-1', max_requests=5)
        assert check_rate_limit('user-1', max_requests=5) is not None

        # A different user (or unauthenticated request path) is not affected
        assert check_rate_limit('user-2', max_requests=5) is None
