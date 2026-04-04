import json
import sys
import os
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import update_invoice_status, get_invoice
from botocore.exceptions import ClientError


def handler(event, context):
    """
    Lambda handler for PATCH /api/invoices/{id}/status — update invoice status.

    Request body (JSON):
        {
            "status": "paid"  // One of: draft, sent, paid, overdue
        }

    Returns:
        200: Updated invoice metadata
        400: Invalid request parameters
        401: Missing or invalid authorization
        404: Invoice not found
        500: Server error
    """
    # CORS headers for all responses
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'PATCH, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    }

    try:
        # Extract HTTP method (supports both API Gateway v1 and v2 formats)
        http_method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod', 'PATCH')

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
        # API Gateway v2 format: pathParameters.id
        # API Gateway v1 format: pathParameters.id
        path_params = event.get('pathParameters', {})
        invoice_id = path_params.get('id') if path_params else None

        if not invoice_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invoice ID is required in path'})
            }

        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)

        new_status = body.get('status')

        if not new_status:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Status is required in request body'})
            }

        # Validate status value
        valid_statuses = ['draft', 'sent', 'paid', 'overdue']
        if new_status not in valid_statuses:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': f"Invalid status '{new_status}'. Must be one of: {', '.join(valid_statuses)}"
                })
            }

        # Check if invoice exists and belongs to user (authorization check)
        existing_invoice = get_invoice(user_id, invoice_id)
        if not existing_invoice:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': f'Invoice {invoice_id} not found'})
            }

        # Verify invoice ownership (defense-in-depth authorization)
        if existing_invoice.get('userId') != user_id:
            return {
                'statusCode': 403,
                'headers': headers,
                'body': json.dumps({'error': 'Unauthorized: invoice does not belong to user'})
            }

        # Calculate overdue status if applicable
        # Overdue logic: status is 'sent' AND dueDate < today
        # This ensures invoices automatically show as overdue when past their due date,
        # even if the client requests status='sent'
        actual_status = new_status
        if new_status == 'sent' and 'dueDate' in existing_invoice:
            try:
                due_date_str = existing_invoice['dueDate']
                # Parse ISO format date, handling both with and without timezone
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                now = datetime.now(due_date.tzinfo) if due_date.tzinfo else datetime.now()

                # If due date has passed, auto-set to overdue instead of sent
                if due_date.date() < now.date():
                    actual_status = 'overdue'
            except (ValueError, AttributeError):
                # If date parsing fails, keep the status as-is (graceful degradation)
                pass

        # Prepare paidAt timestamp if marking as paid
        paid_at = None
        if new_status == 'paid':
            paid_at = datetime.now(timezone.utc).isoformat()

        # Update invoice status in DynamoDB
        try:
            updated_invoice = update_invoice_status(
                user_id=user_id,
                invoice_id=invoice_id,
                status=actual_status,
                paid_at=paid_at
            )

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'invoiceId': invoice_id,
                    'status': updated_invoice.get('status'),
                    'paidAt': updated_invoice.get('paidAt'),
                    'updatedAt': updated_invoice.get('updatedAt')
                })
            }

        except ValueError as e:
            # Handle invoice not found or validation errors
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': str(e)})
            }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except ClientError as e:
        print(f"AWS error in PATCH /api/invoices/{{id}}/status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to update invoice status'})
        }
    except Exception as e:
        print(f"Unhandled error in invoices handler: {str(e)}")
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
