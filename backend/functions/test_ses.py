"""
Test SES Email Sending

Temporary endpoint for verifying SES configuration.
Sends a test email to a specified address.
Requires authentication via X-Test-Secret header.

Usage:
    GET /api/test-ses?to=recipient@example.com
    Headers:
        X-Test-Secret: <secret value from sst secret set TestSesSecret>

Response:
    200: { "message": "Test email sent", "messageId": "..." }
    400: { "error": "Missing 'to' parameter" }
    401: { "error": "Authentication required. Provide X-Test-Secret header." }
    500: { "error": "Failed to send email: ..." }
"""

import json
import sys
import os

# Add parent directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.mail_service import send_email
from botocore.exceptions import ClientError
from sst import Resource


def handler(event, context):
    """
    Lambda handler for SES test endpoint.

    Requires X-Test-Secret header matching TestSesSecret for authentication.

    Query params:
        to: recipient email address (required)

    Returns:
        200: Test email sent successfully
        400: Missing required parameter
        401: Authentication failed
        500: SES send failed
    """
    # Validate authentication header
    headers = event.get('headers') or {}
    provided_secret = headers.get('x-test-secret') or headers.get('X-Test-Secret')
    expected_secret = Resource.TestSesSecret.value

    if not provided_secret or provided_secret != expected_secret:
        return {
            'statusCode': 401,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'Authentication required. Provide X-Test-Secret header.'})
        }

    # Extract recipient from query params
    params = event.get('queryStringParameters') or {}
    to_address = params.get('to')

    if not to_address:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': "Missing 'to' parameter"})
        }

    # Compose test email
    subject = "Invoi SES Test Email"
    body_text = """Hello,

This is a test email from the Invoi application to verify SES configuration.

If you received this email, the following are working correctly:
- SES domain identity verification (goinvoi.com)
- DKIM signing
- Email delivery from noreply@goinvoi.com

Date: 2026-04-03
Source: Invoi Phase 3 SES Configuration

Thank you,
Invoi Team"""

    # Send test email
    try:
        response = send_email(
            to_addresses=[to_address],
            subject=subject,
            body_text=body_text,
            from_email="noreply@goinvoi.com"
        )

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'message': 'Test email sent successfully',
                'messageId': response['MessageId'],
                'recipient': to_address
            })
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']

        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'error': f'Failed to send email: {error_code} - {error_message}'
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'error': f'Unexpected error: {str(e)}'
            })
        }
