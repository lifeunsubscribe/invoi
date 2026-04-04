import json
import sys
import os
import base64
import re
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import get_user, put_user

# S3 client for logo storage
s3_client = boto3.client('s3')

# Get bucket name from SST Resource environment variable
# SST Ion provides bucket name via SST_Resource_<name>_name when linked
BUCKET_NAME = os.environ.get('SST_Resource_InvoiStorage_name')

# Maximum logo file size (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

# Allowed image formats (SVG excluded due to XSS risk - SVG can contain embedded JavaScript)
ALLOWED_FORMATS = ['png', 'jpg', 'jpeg']


def handler(event, context):
    """
    Lambda handler for GET/POST/DELETE /api/logo — retrieve, upload, or remove logo image.

    GET: Retrieve logo from S3 as base64-encoded data URL
    POST: Upload logo to S3, update user record with logoKey and logoSize
    DELETE: Remove logo from S3, clear logoKey from user record

    All methods require valid JWT in Authorization header.
    """
    # CORS headers for all responses
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    }

    try:
        # Extract HTTP method (supports both API Gateway v1 and v2 formats)
        http_method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod', 'POST')

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

        # Route to appropriate handler
        if http_method == 'GET':
            return handle_get(user_id, headers)
        elif http_method == 'POST':
            return handle_upload(user_id, event, headers)
        elif http_method == 'DELETE':
            return handle_delete(user_id, headers)
        else:
            return {
                'statusCode': 405,
                'headers': headers,
                'body': json.dumps({'error': f'Method {http_method} not allowed'})
            }

    except Exception as e:
        # Log error for CloudWatch
        print(f"Unhandled error in logo handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def handle_get(user_id, headers):
    """
    Handle GET /api/logo - retrieve logo from S3 as base64-encoded data URL.

    Returns the logo image as a data URL that can be directly used in <img> src attributes.
    """
    try:
        # Get user record to find logo key
        user = get_user(user_id)

        if not user or not user.get('logoKey'):
            # No logo uploaded
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'No logo found for this user'})
            }

        logo_key = user['logoKey']

        # Fetch logo from S3
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=logo_key)
            logo_bytes = response['Body'].read()
            content_type = response.get('ContentType', 'application/octet-stream')

            # Encode as base64 data URL
            base64_data = base64.b64encode(logo_bytes).decode('utf-8')
            data_url = f"data:{content_type};base64,{base64_data}"

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'logoData': data_url,
                    'logoSize': user.get('logoSize', 'medium'),
                    'logoKey': logo_key
                })
            }

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey':
                # Logo key exists in user record but file is missing from S3
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({'error': 'Logo file not found in storage'})
                }
            else:
                print(f"S3 error fetching logo: {error_code} - {str(e)}")
                return {
                    'statusCode': 500,
                    'headers': headers,
                    'body': json.dumps({'error': 'Failed to retrieve logo from storage'})
                }

    except Exception as e:
        print(f"Unexpected error in logo retrieval: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to retrieve logo'})
        }


def handle_upload(user_id, event, headers):
    """
    Handle POST /api/logo - upload logo image to S3.

    Expects request body with:
    - imageData: base64-encoded image data URL (e.g., "data:image/png;base64,...")
    - logoSize: size preference ("small", "medium", or "large")
    """
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)

        image_data = body.get('imageData')
        logo_size = body.get('logoSize', 'medium')

        # Validate required fields
        if not image_data:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'imageData is required'})
            }

        # Validate logo size
        if logo_size not in ['small', 'medium', 'large']:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'logoSize must be "small", "medium", or "large"'})
            }

        # Parse data URL and extract format and base64 data
        # Expected format: data:image/png;base64,iVBORw0KG...
        data_url_pattern = r'^data:image/(png|jpe?g);base64,(.+)$'
        match = re.match(data_url_pattern, image_data, re.IGNORECASE)

        if not match:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid image data URL format. Expected data:image/[png|jpg];base64,...'})
            }

        format_from_url = match.group(1).lower()
        base64_data = match.group(2)

        # Normalize format (jpeg -> jpg)
        if format_from_url == 'jpeg':
            file_extension = 'jpg'
        else:
            file_extension = format_from_url

        # Validate format
        if file_extension not in ALLOWED_FORMATS:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': f'Image format {file_extension} not allowed. Use PNG or JPG only.'})
            }

        # Decode base64 data
        try:
            image_bytes = base64.b64decode(base64_data)
        except Exception as e:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid base64 encoding'})
            }

        # Validate file size
        if len(image_bytes) > MAX_FILE_SIZE:
            size_mb = len(image_bytes) / (1024 * 1024)
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': f'Image size ({size_mb:.1f}MB) exceeds maximum allowed size (5MB)'})
            }

        # Determine content type for S3
        content_type_map = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg'
        }
        content_type = content_type_map.get(file_extension, 'application/octet-stream')

        # Upload to S3 at users/{userId}/logo.{ext}
        s3_key = f'users/{user_id}/logo.{file_extension}'

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=image_bytes,
            ContentType=content_type,
            Metadata={
                'uploaded-by': user_id,
                'upload-timestamp': str(int(os.times()[4]))  # Unix timestamp
            }
        )

        # Update user record with logo key and size
        user = get_user(user_id)
        if not user:
            # If user doesn't exist yet, create minimal record
            user = {'userId': user_id}

        user['logoKey'] = s3_key
        user['logoSize'] = logo_size

        updated_user = put_user(user)

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'logoKey': s3_key,
                'logoSize': logo_size,
                'message': 'Logo uploaded successfully'
            })
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        print(f"AWS error in logo upload: {error_code} - {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to upload logo to storage'})
        }
    except Exception as e:
        print(f"Unexpected error in logo upload: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to upload logo'})
        }


def handle_delete(user_id, headers):
    """
    Handle DELETE /api/logo - remove logo from S3 and user record.
    """
    try:
        # Get user record to find logo key
        user = get_user(user_id)

        if not user or not user.get('logoKey'):
            # No logo to delete
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'No logo to delete'})
            }

        logo_key = user['logoKey']

        # Delete from S3
        try:
            s3_client.delete_object(
                Bucket=BUCKET_NAME,
                Key=logo_key
            )
        except ClientError as e:
            # Log error but don't fail - we still want to clear the user record
            print(f"S3 delete error (non-fatal): {str(e)}")

        # Clear logo fields from user record
        user['logoKey'] = ''
        user['logoSize'] = 'medium'  # Reset to default

        updated_user = put_user(user)

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'Logo deleted successfully'})
        }

    except ClientError as e:
        print(f"DynamoDB error in logo delete: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to delete logo'})
        }
    except Exception as e:
        print(f"Unexpected error in logo delete: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to delete logo'})
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

    # No valid JWT claims found
    return None
