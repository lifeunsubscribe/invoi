import sys
import os
import pytest
from unittest.mock import MagicMock, patch
import base64

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.s3_utils import fetch_logo_from_s3
from botocore.exceptions import ClientError


class TestFetchLogoFromS3:
    """Tests for fetch_logo_from_s3 utility function"""

    def test_fetch_logo_success(self):
        """Should fetch logo and return base64 data URL"""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_response = {
            'Body': MagicMock(read=lambda: b'fake-image-data'),
            'ContentType': 'image/png'
        }
        mock_s3_client.get_object.return_value = mock_response

        # Call function
        result = fetch_logo_from_s3(mock_s3_client, 'test-bucket', 'users/123/logo.png')

        # Verify S3 client was called correctly
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='users/123/logo.png'
        )

        # Verify result is a base64 data URL
        assert result.startswith('data:image/png;base64,')
        expected_base64 = base64.b64encode(b'fake-image-data').decode('utf-8')
        assert result == f'data:image/png;base64,{expected_base64}'

    def test_fetch_logo_with_default_content_type(self):
        """Should use default content type when not provided"""
        mock_s3_client = MagicMock()
        mock_response = {
            'Body': MagicMock(read=lambda: b'fake-data'),
            # No ContentType key
        }
        mock_s3_client.get_object.return_value = mock_response

        result = fetch_logo_from_s3(mock_s3_client, 'test-bucket', 'users/123/logo.png')

        # Should default to application/octet-stream
        assert result.startswith('data:application/octet-stream;base64,')

    def test_fetch_logo_s3_error(self):
        """Should raise ClientError when S3 operation fails"""
        mock_s3_client = MagicMock()
        mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey'}},
            'GetObject'
        )

        with pytest.raises(ClientError):
            fetch_logo_from_s3(mock_s3_client, 'test-bucket', 'users/123/missing.png')
