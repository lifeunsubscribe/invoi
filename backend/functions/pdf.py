import json
import logging
import sys
import os
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import get_invoice
from services.logging_config import setup_logging

# Configure logging for this Lambda function
setup_logging()
logger = logging.getLogger(__name__)

# Initialize S3 client
s3_client = boto3.client('s3')


def handler(event, context):
    """
    Lambda handler for GET /api/pdf/{invoiceId} — return signed S3 URL for PDF download.

    Returns:
        200: Signed S3 URL (valid for 15 minutes)
        400: Missing invoice ID in path
        401: Missing or invalid authorization
        404: Invoice not found, not owned by user, or PDF not available
        500: Server error
    """
    # CORS headers for all responses
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    }

    try:
        # Extract HTTP method (supports both API Gateway v1 and v2 formats)
        http_method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod', 'GET')

        # Handle CORS preflight requests before auth check
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': ''
            }

        # Extract userId from JWT claims
        auth_header = event.get('headers', {}).get('authorization') or event.get('headers', {}).get('Authorization')

        if not auth_header:
            return {
                'statusCode': 401,
                'headers': headers,
                'body': json.dumps({'error': 'Missing Authorization header'})
            }

        user_id = _extract_user_id_from_token(event)

        if not user_id:
            return {
                'statusCode': 401,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid or expired token'})
            }

        # Extract invoice ID from path parameters
        path_params = event.get('pathParameters', {})
        invoice_id = path_params.get('id') if path_params else None

        if not invoice_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invoice ID is required in path'})
            }

        # Extract optional PDF type from query parameters (invoice or log)
        # Defaults to 'invoice' for backward compatibility
        query_params = event.get('queryStringParameters') or {}
        pdf_type = query_params.get('type', 'invoice')

        if pdf_type not in ['invoice', 'log']:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid PDF type. Must be "invoice" or "log"'})
            }

        # Retrieve invoice from DynamoDB
        invoice = get_invoice(user_id, invoice_id)

        # Return 404 for both non-existent invoices AND invoices not owned by user
        # to prevent invoice ID enumeration attacks
        if not invoice or invoice.get('userId') != user_id:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': f'Invoice {invoice_id} not found'})
            }

        # Extract PDF S3 key from invoice record based on requested type
        if pdf_type == 'log':
            pdf_key = invoice.get('logPdfKey')
            pdf_description = 'Service log PDF'
        else:
            pdf_key = invoice.get('pdfKey')
            pdf_description = 'Invoice PDF'

        if not pdf_key:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': f'{pdf_description} not available for this invoice'})
            }

        # Get S3 bucket name from environment (provided by SST link)
        bucket_name = os.environ.get('InvoiStorage')

        if not bucket_name:
            logger.error("InvoiStorage bucket name not found in environment")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Storage configuration error'})
            }

        # Generate signed S3 URL with 15-minute expiration
        try:
            signed_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': pdf_key
                },
                ExpiresIn=900  # 15 minutes in seconds
            )

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'invoiceId': invoice_id,
                    'pdfUrl': signed_url,
                    'expiresIn': 900
                })
            }

        except ClientError as e:
            logger.error(f"S3 error generating presigned URL: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Failed to generate download URL'})
            }

    except ClientError as e:
        logger.error(f"DynamoDB error in GET /api/pdf/{{id}}: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to retrieve invoice'})
        }
    except Exception as e:
        logger.error(f"Unhandled error in pdf handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def _extract_user_id_from_token(event):
    """
    Extract userId from JWT token claims.

    Returns None if no valid JWT claims are present.
    """
    # Check for Cognito authorizer claims (API Gateway v2 with JWT authorizer)
    try:
        claims = event.get('requestContext', {}).get('authorizer', {}).get('jwt', {}).get('claims', {})
        if claims and 'sub' in claims:
            return claims.get('sub')
    except (KeyError, AttributeError):
        pass

    # Fallback: check for lambda authorizer format (API Gateway v1)
    try:
        authorizer = event.get('requestContext', {}).get('authorizer', {})
        if authorizer and 'claims' in authorizer and 'sub' in authorizer['claims']:
            return authorizer['claims'].get('sub')
    except (KeyError, AttributeError):
        pass

    return None
