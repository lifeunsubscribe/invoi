"""
S3 utility functions.

Shared utilities for interacting with S3 storage across Lambda functions.
"""
import base64
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def fetch_logo_from_s3(s3_client, bucket_name, logo_key):
    """
    Fetch logo image from S3 and return as base64-encoded data URL.

    Args:
        s3_client: boto3.client('s3') - S3 client instance
        bucket_name: str - S3 bucket name
        logo_key: str - S3 key for logo (e.g., users/{userId}/logo.png)

    Returns:
        str - Base64-encoded data URL (e.g., data:image/png;base64,...)
        None - If logo cannot be fetched

    Raises:
        ClientError - If S3 operation fails
    """
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
