import json
import logging
import sys
import os
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import update_invoice_status, get_invoice, query_invoices
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def handler(event, context):
    """
    Lambda handler for invoice endpoints:
    - GET /api/invoices — list invoices with filtering and pagination
    - GET /api/invoices/{id} — retrieve single invoice
    - PATCH /api/invoices/{id}/status — update invoice status

    Returns:
        200: Success with invoice data
        400: Invalid request parameters
        401: Missing or invalid authorization
        404: Invoice not found
        500: Server error
    """
    # CORS headers for all responses
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, PATCH, OPTIONS',
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

        # Route to appropriate handler based on HTTP method and path
        path_params = event.get('pathParameters', {})
        invoice_id = path_params.get('id') if path_params else None

        if http_method == 'GET':
            if invoice_id:
                return _handle_get_single_invoice(event, headers)
            else:
                return _handle_list_invoices(event, headers)
        elif http_method == 'PATCH':
            return _handle_patch_status(event, headers)
        else:
            return {
                'statusCode': 405,
                'headers': headers,
                'body': json.dumps({'error': f'Method {http_method} not allowed'})
            }

    except Exception as e:
        logger.error(f"Unhandled error in invoices handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def _handle_list_invoices(event, headers):
    """
    Handle GET /api/invoices — list invoices with filtering and pagination.

    Query parameters:
        - status: comma-separated status values (e.g., "sent,paid")
        - clientId: filter by client ID
        - start: start date in YYYY-MM-DD format (inclusive)
        - end: end date in YYYY-MM-DD format (inclusive)
        - limit: max number of results (default: 100, max: 1000)
        - offset: number of results to skip (default: 0)

    Returns:
        200: Array of invoice records
        400: Invalid query parameters
        401: Missing or invalid authorization
        500: Server error
    """
    try:
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

        # Extract and parse query parameters
        query_params = event.get('queryStringParameters') or {}

        filters = {}

        # Parse status filter (comma-separated list)
        if 'status' in query_params:
            status_param = query_params['status']
            # For now, only support single status filter
            # (DynamoDB FilterExpression doesn't support IN operator easily)
            # We'll filter in application code if multiple statuses requested
            filters['status'] = status_param

        # Parse clientId filter
        if 'clientId' in query_params:
            filters['clientId'] = query_params['clientId']

        # Parse date range filters (convert YYYY-MM-DD to invoiceId format)
        if 'start' in query_params or 'end' in query_params:
            start_date = query_params.get('start')
            end_date = query_params.get('end')

            # Validate date format (YYYY-MM-DD)
            if start_date:
                try:
                    # Convert YYYY-MM-DD to INV-YYYYMMDD format
                    date_obj = datetime.fromisoformat(start_date)
                    filters['invoiceId_start'] = f"INV-{date_obj.strftime('%Y%m%d')}"
                except ValueError:
                    return {
                        'statusCode': 400,
                        'headers': headers,
                        'body': json.dumps({'error': 'Invalid start date format. Use YYYY-MM-DD'})
                    }

            if end_date:
                try:
                    # Convert YYYY-MM-DD to INV-YYYYMMDD format
                    date_obj = datetime.fromisoformat(end_date)
                    filters['invoiceId_end'] = f"INV-{date_obj.strftime('%Y%m%d')}"
                except ValueError:
                    return {
                        'statusCode': 400,
                        'headers': headers,
                        'body': json.dumps({'error': 'Invalid end date format. Use YYYY-MM-DD'})
                    }

        # Parse pagination parameters
        try:
            limit = int(query_params.get('limit', 100))
            offset = int(query_params.get('offset', 0))

            # Enforce limits
            if limit < 1 or limit > 1000:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Limit must be between 1 and 1000'})
                }

            if offset < 0:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Offset must be non-negative'})
                }

        except ValueError:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Limit and offset must be integers'})
            }

        # Query invoices from DynamoDB
        all_invoices = query_invoices(user_id, filters if filters else None)

        # Handle multi-status filtering in application code
        # (since DynamoDB FilterExpression doesn't easily support OR conditions)
        status_param = query_params.get('status', '')
        if status_param and ',' in status_param:
            requested_statuses = [s.strip() for s in status_param.split(',')]
            all_invoices = [inv for inv in all_invoices if inv.get('status') in requested_statuses]

        # Apply pagination in application code
        total_count = len(all_invoices)
        paginated_invoices = all_invoices[offset:offset + limit]

        # Return paginated results with metadata
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'invoices': paginated_invoices,
                'pagination': {
                    'total': total_count,
                    'limit': limit,
                    'offset': offset,
                    'hasMore': (offset + limit) < total_count
                }
            })
        }

    except ClientError as e:
        logger.error(f"DynamoDB error in GET /api/invoices: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to query invoices'})
        }
    except Exception as e:
        logger.error(f"Error in list invoices handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def _handle_get_single_invoice(event, headers):
    """
    Handle GET /api/invoices/{id} — retrieve single invoice with full metadata.

    Returns:
        200: Invoice record with full metadata
        401: Missing or invalid authorization
        404: Invoice not found
        500: Server error
    """
    try:
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

        # Retrieve invoice from DynamoDB
        invoice = get_invoice(user_id, invoice_id)

        if not invoice:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': f'Invoice {invoice_id} not found'})
            }

        # Verify invoice ownership (defense-in-depth authorization)
        if invoice.get('userId') != user_id:
            return {
                'statusCode': 403,
                'headers': headers,
                'body': json.dumps({'error': 'Unauthorized: invoice does not belong to user'})
            }

        # Return full invoice metadata
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(invoice)
        }

    except ClientError as e:
        logger.error(f"DynamoDB error in GET /api/invoices/{{id}}: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to retrieve invoice'})
        }
    except Exception as e:
        logger.error(f"Error in get single invoice handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def _handle_patch_status(event, headers):
    """
    Handle PATCH /api/invoices/{id}/status — update invoice status.

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
    try:
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
        logger.error(f"AWS error in PATCH /api/invoices/{{id}}/status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to update invoice status'})
        }
    except Exception as e:
        logger.error(f"Error in patch status handler: {str(e)}")
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
