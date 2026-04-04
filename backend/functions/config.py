import json
import logging
import re
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import get_user, put_user
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def handler(event, context):
    """
    Lambda handler for GET/POST /api/config — user profile management.

    GET: Returns user profile from DynamoDB
    POST: Updates user profile in DynamoDB

    Both methods require valid JWT in Authorization header.
    """
    # CORS headers for all responses
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
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
        # TODO: Once Cognito is set up in Phase 1, this will come from:
        # event['requestContext']['authorizer']['jwt']['claims']['sub']
        # For now, check Authorization header exists (case-insensitive check)
        auth_header = event.get('headers', {}).get('authorization') or event.get('headers', {}).get('Authorization')

        if not auth_header:
            return {
                'statusCode': 401,
                'headers': headers,
                'body': json.dumps({'error': 'Missing Authorization header'})
            }

        # Extract userId from token claims (Cognito integration)
        # TODO: Replace this stub with actual Cognito claim extraction in Phase 1
        user_id = _extract_user_id_from_token(event)

        if not user_id:
            return {
                'statusCode': 401,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid or expired token'})
            }

        # Route to appropriate handler
        if http_method == 'GET':
            return handle_get(user_id, headers)
        elif http_method == 'POST':
            return handle_post(user_id, event, headers)
        else:
            return {
                'statusCode': 405,
                'headers': headers,
                'body': json.dumps({'error': f'Method {http_method} not allowed'})
            }

    except Exception as e:
        # Log error for CloudWatch
        logger.error(f"Unhandled error in config handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def handle_get(user_id, headers):
    """
    Handle GET /api/config - retrieve user profile.

    Returns existing profile if found in DynamoDB, otherwise returns default profile
    with sensible defaults for new users.
    """
    try:
        user = get_user(user_id)

        if not user:
            # Return default profile for new users (not yet saved to DB)
            user = get_default_profile(user_id)

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(user)
        }

    except ClientError as e:
        logger.error(f"DynamoDB error in GET /api/config: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to retrieve user profile'})
        }


def handle_post(user_id, event, headers):
    """
    Handle POST /api/config - update user profile.

    Validates required fields (name, email, rate) and updates user record in DynamoDB.
    """
    try:
        # Parse request body (API Gateway may pass as string or already-parsed dict)
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)

        # Validate required fields
        validation_error = validate_profile_fields(body)
        if validation_error:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': validation_error})
            }

        # Allowlist only valid profile fields to prevent arbitrary field injection
        # userId comes from token, ensuring users can only update their own profile
        allowed_fields = [
            'name', 'email', 'rate', 'address', 'personalEmail', 'agency',
            'accountantEmail', 'invoiceNote', 'saveFolder', 'clientName',
            'clientEmail', 'occupation', 'accent', 'template', 'signatureFont',
            'clients', 'activeClientId', 'invoiceNumberConfig', 'logoKey', 'logoSize'
        ]
        user_data = {
            'userId': user_id
        }
        for field in allowed_fields:
            if field in body:
                # Normalize rate to float to ensure consistent storage type
                if field == 'rate':
                    user_data[field] = float(body[field])
                else:
                    user_data[field] = body[field]

        # Update user profile in DynamoDB (put_user handles create or update)
        updated_user = put_user(user_data)

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(updated_user)
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except ClientError as e:
        logger.error(f"DynamoDB error in POST /api/config: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to update user profile'})
        }
    except Exception as e:
        logger.error(f"Unexpected error in POST /api/config: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to update user profile'})
        }


def validate_profile_fields(data):
    """
    Validate required profile fields.

    Returns error message if validation fails, None if valid.
    """
    # Validate name
    name = data.get('name', '').strip()
    if not name:
        return 'Name is required and cannot be empty'

    # Validate email
    email = data.get('email', '').strip()
    if not email:
        return 'Email is required and cannot be empty'

    # Basic email format validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return 'Email must be a valid email address'

    # Validate rate (required field, must be positive number)
    rate = data.get('rate')
    if rate is None:
        return 'Rate is required'

    # Convert to float and validate (handles both numeric and string inputs)
    try:
        rate_float = float(rate)
        if rate_float <= 0:
            return 'Rate must be a positive number'
    except (ValueError, TypeError):
        return 'Rate must be a valid number'

    return None


def get_default_profile(user_id):
    """
    Generate default profile for new users.

    Returns a profile structure with sensible defaults matching the Users table schema.
    This profile is NOT saved to DynamoDB — it's returned on first GET and the user
    must POST to save their actual profile data.
    """
    return {
        'userId': user_id,
        'email': '',
        'name': '',
        'address': '',
        'personalEmail': '',
        'rate': 0,
        'occupation': 'other',
        'accent': '#b76e79',
        'template': 'morning-light',
        'invoiceNote': '',
        'signatureFont': 'Dancing Script',
        'accountantEmail': '',
        'invoiceNumberConfig': {
            'prefix': 'INV',
            'includeYear': False,
            'separator': '-',
            'padding': 3,
            'nextNum': 1
        },
        'paymentTerms': 'receipt',
        'taxEnabled': False,
        'taxRate': 0,
        'taxLabel': 'Sales Tax',
        'logoKey': '',
        'logoSize': 'medium',
        'clients': [],
        'activeClientId': ''
    }


def _extract_user_id_from_token(event):
    """
    Extract userId from JWT token claims.

    Requires properly validated Cognito JWT claims from API Gateway authorizer.
    This extracts the user ID from:
    - event['requestContext']['authorizer']['jwt']['claims']['sub'] (API Gateway v2)
    - event['requestContext']['authorizer']['claims']['sub'] (API Gateway v1/Lambda authorizer)

    Returns None if no valid JWT claims are present (will result in 401 response).
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

    # No valid JWT claims found - authentication required
    return None
