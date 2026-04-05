import json
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import query_invoices
from services.logging_config import setup_logging
from botocore.exceptions import ClientError

# Configure logging for this Lambda function
setup_logging()
logger = logging.getLogger(__name__)


def handler(event, context):
    """
    Lambda handler for GET /api/scan-month — scan for existing weekly invoices in a given month.

    Query parameters:
        year (required): 4-digit year (e.g., 2026)
        month (required): month number 1-12

    Returns:
        200: Array of invoice metadata for the specified month
        400: Invalid query parameters
        401: Missing or invalid authorization
        500: Server error

    Note: CORS is handled by API Gateway (configured in sst.config.ts).
    Lambda functions should not set CORS headers.
    """
    # Response headers
    headers = {
        'Content-Type': 'application/json',
    }

    try:
        # Extract HTTP method (supports both API Gateway v1 and v2 formats)
        http_method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod', 'GET')

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

        # Extract and validate query parameters
        query_params = event.get('queryStringParameters') or {}
        year = query_params.get('year')
        month = query_params.get('month')

        if not year or not month:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Both year and month query parameters are required'})
            }

        # Validate year and month
        try:
            year_int = int(year)
            month_int = int(month)

            if year_int < 1900 or year_int > 2100:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Year must be between 1900 and 2100'})
                }

            if month_int < 1 or month_int > 12:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Month must be between 1 and 12'})
                }
        except ValueError:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Year and month must be valid integers'})
            }

        # Construct invoiceId range for the month
        # Format: INV-YYYYMMDD (e.g., INV-20260301 to INV-20260331)
        # Using day 01-31 covers all possible dates in any month
        invoice_id_start = f"INV-{year_int:04d}{month_int:02d}01"
        invoice_id_end = f"INV-{year_int:04d}{month_int:02d}31"

        # Query DynamoDB for invoices in this date range
        invoices = query_invoices(
            user_id,
            filters={
                'invoiceId_start': invoice_id_start,
                'invoiceId_end': invoice_id_end,
                'type': 'weekly'  # Only weekly invoices (exclude monthly reports)
            }
        )

        # Return invoice metadata (not full PDF content)
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(invoices)
        }

    except ClientError as e:
        logger.error(f"DynamoDB error in GET /api/scan-month: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to query invoices'})
        }
    except Exception as e:
        logger.error(f"Unhandled error in scan_month handler: {str(e)}")
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
