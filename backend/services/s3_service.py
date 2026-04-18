"""
S3 Service

Provides shared S3 operations for the Invoi backend.

Main Functions:
    fetch_logo_from_s3(logo_key, bucket_name) -> str
        Fetches logo image from S3 and returns as base64-encoded data URL.

Helpers:
    _get_s3_client() -> boto3.client
        Lazy-initialize S3 client.
    _reset_s3_client() -> None
        Reset S3 client for test isolation.
"""

import os
import logging
import base64
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# S3 client for lazy initialization
_s3_client = None


def _get_s3_client():
    """Lazy-initialize S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3')
    return _s3_client


def _reset_s3_client():
    """Reset S3 client to None for test isolation."""
    global _s3_client
    _s3_client = None


def fetch_logo_from_s3(logo_key, bucket_name=None):
    """
    Fetch logo image from S3 and return as base64-encoded data URL.

    Args:
        logo_key: str - S3 key for logo (e.g., users/{userId}/logo.png)
        bucket_name: str - S3 bucket name (defaults to SST_Resource_InvoiStorage_name env var)

    Returns:
        str - Base64-encoded data URL (e.g., data:image/png;base64,...)
        None - If logo cannot be fetched

    Raises:
        ClientError - If S3 operation fails
    """
    # Default to SST Ion resource bucket name if not provided
    if bucket_name is None:
        bucket_name = os.environ.get('SST_Resource_InvoiStorage_name')

    if not bucket_name:
        raise ValueError("bucket_name must be provided or SST_Resource_InvoiStorage_name must be set")

    s3_client = _get_s3_client()

    try:
        # Fetch logo from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=logo_key)
        logo_bytes = response['Body'].read()
        content_type = response.get('ContentType', 'application/octet-stream')

        # Encode as base64 data URL
        base64_data = base64.b64encode(logo_bytes).decode('utf-8')
        data_url = f"data:{content_type};base64,{base64_data}"

        return data_url

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        logger.warning(f"Failed to fetch logo from S3 (key: {logo_key}): {error_code}")
        raise
