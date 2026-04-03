import json
import os
import sys

# Add parent directory to path for service imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import get_user
from botocore.exceptions import ClientError


def handler(event, context):
    """
    Lambda handler for GET /api/config — returns user profile from DynamoDB.

    This is the first protected endpoint using Cognito JWT. The user ID is
    extracted from JWT claims and used to fetch the user's profile.

    Returns:
        - 200: User profile JSON (existing user or defaults for new user)
        - 401: Missing or invalid authentication
        - 500: Server error
    """

    # Set CORS headers (will match CloudFront origin in production)
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    }

    try:
        # Extract user ID from Cognito JWT claims
        # API Gateway authorizer places claims in requestContext.authorizer.claims
        user_id = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer'].get('claims', {})
            user_id = claims.get('sub')

        if not user_id:
            return {
                'statusCode': 401,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Unauthorized',
                    'message': 'Valid JWT required'
                })
            }

        # Fetch user profile from DynamoDB
        user_profile = get_user(user_id)

        if user_profile:
            # User exists - return their profile
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps(user_profile)
            }
        else:
            # New user - return default profile structure
            default_profile = {
                'userId': user_id,
                'email': '',
                'name': '',
                'address': '',
                'personalEmail': '',
                'rate': 0.0,
                'occupation': '',
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
                'activeClientId': '',
                'plan': 'free'
            }

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps(default_profile)
            }

    except ClientError as e:
        # DynamoDB error
        error_code = e.response['Error']['Code']
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Database error',
                'message': f'Failed to retrieve user profile: {error_code}'
            })
        }

    except Exception as e:
        # Unexpected error
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }
