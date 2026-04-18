"""
Tests for s3_service.py

Tests S3 operations including logo fetching.
S3 API calls are mocked to avoid actual S3 operations during tests.
"""

import pytest
import os
import base64
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.s3_service import fetch_logo_from_s3, get_s3_client, get_bucket_name, _reset_s3_client


class TestFetchLogoFromS3:
    """Tests for fetch_logo_from_s3() function"""

    @patch('services.s3_service._get_s3_client')
    def test_fetch_logo_success_png(self, mock_get_s3_client):
        """Test successful logo fetch for PNG image"""
        # Mock S3 client response
        mock_s3 = MagicMock()
        mock_response = {
            'Body': MagicMock(),
            'ContentType': 'image/png'
        }
        # Create fake PNG data
        fake_png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        mock_response['Body'].read.return_value = fake_png_data
        mock_s3.get_object.return_value = mock_response
        mock_get_s3_client.return_value = mock_s3

        # Fetch logo
        with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': 'test-bucket'}):
            result = fetch_logo_from_s3('users/user-123/logo.png')

        # Verify S3 was called correctly
        mock_s3.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='users/user-123/logo.png'
        )

        # Verify result is a base64-encoded data URL
        assert result.startswith('data:image/png;base64,')
        expected_b64 = base64.b64encode(fake_png_data).decode('utf-8')
        assert result == f'data:image/png;base64,{expected_b64}'

    @patch('services.s3_service._get_s3_client')
    def test_fetch_logo_success_jpeg(self, mock_get_s3_client):
        """Test successful logo fetch for JPEG image"""
        # Mock S3 client response
        mock_s3 = MagicMock()
        mock_response = {
            'Body': MagicMock(),
            'ContentType': 'image/jpeg'
        }
        fake_jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        mock_response['Body'].read.return_value = fake_jpeg_data
        mock_s3.get_object.return_value = mock_response
        mock_get_s3_client.return_value = mock_s3

        # Fetch logo
        result = fetch_logo_from_s3('users/user-456/logo.jpg', bucket_name='custom-bucket')

        # Verify S3 was called with custom bucket
        mock_s3.get_object.assert_called_once_with(
            Bucket='custom-bucket',
            Key='users/user-456/logo.jpg'
        )

        # Verify result is a base64-encoded data URL
        assert result.startswith('data:image/jpeg;base64,')
        expected_b64 = base64.b64encode(fake_jpeg_data).decode('utf-8')
        assert result == f'data:image/jpeg;base64,{expected_b64}'

    @patch('services.s3_service._get_s3_client')
    def test_fetch_logo_missing_content_type(self, mock_get_s3_client):
        """Test logo fetch when ContentType is missing (defaults to application/octet-stream)"""
        # Mock S3 client response without ContentType
        mock_s3 = MagicMock()
        mock_response = {
            'Body': MagicMock()
            # No ContentType field
        }
        fake_data = b'fake logo data'
        mock_response['Body'].read.return_value = fake_data
        mock_s3.get_object.return_value = mock_response
        mock_get_s3_client.return_value = mock_s3

        # Fetch logo
        with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': 'test-bucket'}):
            result = fetch_logo_from_s3('users/user-789/logo.bin')

        # Verify result uses default content type
        assert result.startswith('data:application/octet-stream;base64,')

    @patch('services.s3_service._get_s3_client')
    def test_fetch_logo_s3_not_found(self, mock_get_s3_client):
        """Test logo fetch when S3 object does not exist"""
        # Mock S3 client to raise NoSuchKey error
        mock_s3 = MagicMock()
        error_response = {
            'Error': {
                'Code': 'NoSuchKey',
                'Message': 'The specified key does not exist.'
            }
        }
        mock_s3.get_object.side_effect = ClientError(error_response, 'GetObject')
        mock_get_s3_client.return_value = mock_s3

        # Fetch logo should raise ClientError
        with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': 'test-bucket'}):
            with pytest.raises(ClientError) as exc_info:
                fetch_logo_from_s3('users/user-999/nonexistent.png')

        # Verify error code
        assert exc_info.value.response['Error']['Code'] == 'NoSuchKey'

    @patch('services.s3_service._get_s3_client')
    def test_fetch_logo_s3_access_denied(self, mock_get_s3_client):
        """Test logo fetch when access is denied"""
        # Mock S3 client to raise AccessDenied error
        mock_s3 = MagicMock()
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access Denied'
            }
        }
        mock_s3.get_object.side_effect = ClientError(error_response, 'GetObject')
        mock_get_s3_client.return_value = mock_s3

        # Fetch logo should raise ClientError
        with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': 'test-bucket'}):
            with pytest.raises(ClientError) as exc_info:
                fetch_logo_from_s3('users/user-000/logo.png')

        # Verify error code
        assert exc_info.value.response['Error']['Code'] == 'AccessDenied'

    def test_fetch_logo_no_bucket_name(self):
        """Test logo fetch fails when no bucket name is provided"""
        # No bucket_name parameter and no env var
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="bucket_name must be provided"):
                fetch_logo_from_s3('users/user-123/logo.png')

    @patch('services.s3_service._get_s3_client')
    def test_fetch_logo_uses_env_var_bucket(self, mock_get_s3_client):
        """Test logo fetch uses SST_Resource_InvoiStorage_name env var when no bucket_name provided"""
        # Mock S3 client response
        mock_s3 = MagicMock()
        mock_response = {
            'Body': MagicMock(),
            'ContentType': 'image/png'
        }
        mock_response['Body'].read.return_value = b'fake data'
        mock_s3.get_object.return_value = mock_response
        mock_get_s3_client.return_value = mock_s3

        # Fetch logo with env var bucket
        with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': 'env-bucket'}):
            fetch_logo_from_s3('users/user-123/logo.png')

        # Verify env var bucket was used
        mock_s3.get_object.assert_called_once()
        call_kwargs = mock_s3.get_object.call_args[1]
        assert call_kwargs['Bucket'] == 'env-bucket'


class TestGetS3Client:
    """Tests for get_s3_client() function"""

    def test_get_s3_client_returns_client(self):
        """Test that get_s3_client() returns a boto3 S3 client"""
        # Reset client to ensure fresh initialization
        _reset_s3_client()

        with patch('services.s3_service.boto3') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            # Get client
            client = get_s3_client()

            # Verify boto3.client was called with 's3'
            mock_boto3.client.assert_called_once_with('s3')
            assert client == mock_client

    def test_get_s3_client_lazy_initialization(self):
        """Test that get_s3_client() reuses the same client instance"""
        # Reset client to ensure fresh initialization
        _reset_s3_client()

        with patch('services.s3_service.boto3') as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            # Get client multiple times
            client1 = get_s3_client()
            client2 = get_s3_client()

            # Verify boto3.client was called only once (lazy initialization)
            mock_boto3.client.assert_called_once_with('s3')
            assert client1 is client2


class TestGetBucketName:
    """Tests for get_bucket_name() function"""

    def test_get_bucket_name_success(self):
        """Test successful bucket name retrieval from environment"""
        with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': 'my-test-bucket'}):
            bucket_name = get_bucket_name()
            assert bucket_name == 'my-test-bucket'

    def test_get_bucket_name_missing_env_var(self):
        """Test get_bucket_name() raises ValueError when env var is not set"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="SST_Resource_InvoiStorage_name environment variable must be set"):
                get_bucket_name()

    def test_get_bucket_name_empty_env_var(self):
        """Test get_bucket_name() raises ValueError when env var is empty"""
        with patch.dict(os.environ, {'SST_Resource_InvoiStorage_name': ''}):
            with pytest.raises(ValueError, match="SST_Resource_InvoiStorage_name environment variable must be set"):
                get_bucket_name()
