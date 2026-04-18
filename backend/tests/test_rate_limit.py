import os
import re
import pytest


class TestRateLimitConfiguration:
    """Tests for API Gateway rate limiting configuration"""

    @pytest.fixture
    def sst_config_path(self):
        """Path to sst.config.ts file"""
        # Navigate up two levels from backend/tests/ to project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        return os.path.join(project_root, 'sst.config.ts')

    @pytest.fixture
    def sst_config_content(self, sst_config_path):
        """Read sst.config.ts file content"""
        with open(sst_config_path, 'r') as f:
            return f.read()

    def test_rate_limiting_configured(self, sst_config_content):
        """Verify API Gateway has throttling configured"""
        # Check for throttlingRateLimit setting
        assert 'throttlingRateLimit' in sst_config_content, \
            "API Gateway throttlingRateLimit not found in sst.config.ts"

        # Check for throttlingBurstLimit setting
        assert 'throttlingBurstLimit' in sst_config_content, \
            "API Gateway throttlingBurstLimit not found in sst.config.ts"

    def test_rate_limit_values(self, sst_config_content):
        """Verify rate limit values match requirements"""
        # Extract throttlingRateLimit value
        rate_match = re.search(r'throttlingRateLimit:\s*(\d+)', sst_config_content)
        assert rate_match is not None, "throttlingRateLimit value not found"
        rate_limit = int(rate_match.group(1))

        # Extract throttlingBurstLimit value
        burst_match = re.search(r'throttlingBurstLimit:\s*(\d+)', sst_config_content)
        assert burst_match is not None, "throttlingBurstLimit value not found"
        burst_limit = int(burst_match.group(1))

        # Verify values match acceptance criteria
        assert rate_limit == 100, \
            f"Expected throttlingRateLimit=100, got {rate_limit}"
        assert burst_limit == 200, \
            f"Expected throttlingBurstLimit=200, got {burst_limit}"

    def test_rate_limiting_on_api_gateway_v2(self, sst_config_content):
        """Verify rate limiting is configured on ApiGatewayV2 (HTTP API)"""
        # Ensure we're using ApiGatewayV2, not REST API
        assert 'sst.aws.ApiGatewayV2' in sst_config_content, \
            "Expected ApiGatewayV2 (HTTP API) in configuration"

        # Verify throttling is in defaultRouteSettings
        assert 'defaultRouteSettings' in sst_config_content, \
            "defaultRouteSettings not found - throttling must be configured here for HTTP API"

    def test_documentation_includes_limitations(self, sst_config_content):
        """Verify documentation mentions HTTP API limitations"""
        # Check for documentation about HTTP API limitations
        # (HTTP API v2 doesn't support custom rate limit headers)
        assert 'HTTP API' in sst_config_content or 'ApiGatewayV2' in sst_config_content, \
            "Configuration should document API Gateway type"

        # Check that stage-level throttling is documented
        assert 'stage' in sst_config_content.lower(), \
            "Configuration should document stage-level throttling"

    def test_rate_limiting_protects_against_abuse(self, sst_config_content):
        """Verify rate limiting is configured to prevent abuse"""
        # Rate limit should be reasonable (not too high, not too low)
        rate_match = re.search(r'throttlingRateLimit:\s*(\d+)', sst_config_content)
        assert rate_match is not None
        rate_limit = int(rate_match.group(1))

        # Should be between 10 and 10000 requests/second
        # Too low = legitimate users blocked, too high = doesn't prevent abuse
        assert 10 <= rate_limit <= 10000, \
            f"Rate limit {rate_limit} req/s seems unreasonable"

        # Burst should be >= rate limit (allows traffic spikes)
        burst_match = re.search(r'throttlingBurstLimit:\s*(\d+)', sst_config_content)
        assert burst_match is not None
        burst_limit = int(burst_match.group(1))

        assert burst_limit >= rate_limit, \
            f"Burst limit ({burst_limit}) should be >= rate limit ({rate_limit})"
