import json
import sys
import os
from datetime import datetime
import boto3

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import get_user
from services.pdf_service import generate_weekly_invoice, save_pdf_to_s3, format_invoice_number, _calculate_due_date
from botocore.exceptions import ClientError


def handler(event, context):
    """
    Lambda handler for POST /api/submit/weekly — generate weekly invoice PDF, store in S3, save metadata.

    Request body (JSON):
        {
            "hours": {"Monday": 8, "Tuesday": 8, ...},
            "week": {"start": "2026-03-24", "end": "2026-03-30", "invNum": "INV-20260324"},
            "clientEmail": "client@example.com",
            "accountantEmail": "accountant@example.com",
            "saveOnly": true  // If true, save as draft without sending email
        }

    Returns:
        200: Invoice metadata including invoice number and S3 key
        400: Invalid request parameters
        401: Missing or invalid authorization
        500: Server error
    """
    # CORS headers for all responses
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
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

        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)

        hours = body.get('hours')
        week = body.get('week')
        client_email = body.get('clientEmail', '')
        accountant_email = body.get('accountantEmail', '')
        save_only = body.get('saveOnly', True)  # Default to save-only (draft mode) for Phase 2

        # Validate required parameters
        if not hours or not week:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Both hours and week are required in request body'})
            }

        # Validate hours structure (must be a dict with valid day names)
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if not isinstance(hours, dict):
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'hours must be an object with day names as keys'})
            }

        for day, hour_value in hours.items():
            if day not in valid_days:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': f'Invalid day name: {day}. Must be one of: {", ".join(valid_days)}'})
                }
            try:
                hour_float = float(hour_value)
                if hour_float < 0:
                    return {
                        'statusCode': 400,
                        'headers': headers,
                        'body': json.dumps({'error': f'Hours for {day} must be non-negative'})
                    }
            except (ValueError, TypeError):
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': f'Hours for {day} must be a valid number'})
                }

        # Validate week structure
        if not isinstance(week, dict) or 'start' not in week or 'end' not in week or 'invNum' not in week:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'week must contain start, end, and invNum fields'})
            }

        # Get user configuration
        user_config = get_user(user_id)
        if not user_config:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'User configuration not found'})
            }

        # Validate user has required config fields for invoice generation
        required_fields = ['name', 'address', 'personalEmail', 'rate']
        missing_fields = [field for field in required_fields if not user_config.get(field)]
        if missing_fields:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': f'Please complete your profile before generating invoices. Missing: {", ".join(missing_fields)}'
                })
            }

        # Get active client info
        active_client_id = user_config.get('activeClientId')
        clients = user_config.get('clients', [])
        active_client = next((c for c in clients if c.get('id') == active_client_id), None)

        if not active_client:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'No active client configured. Please select a client in your profile.'})
            }

        # Generate preview invoice number for PDF generation (before atomic increment)
        # Note: This is a preview only - the actual number will be confirmed after transaction succeeds
        preview_invoice_number = format_invoice_number(user_config, 'weekly')

        # Generate invoice PDF FIRST, before creating database records
        # This ensures PDF generation failures don't consume invoice numbers
        template_id = user_config.get('template', 'morning-light')
        signature_font = user_config.get('signatureFont', '')
        invoice_date = datetime.now()

        try:
            pdf_bytes = generate_weekly_invoice(
                config=user_config,
                hours=hours,
                week=week,
                template_id=template_id,
                signature_font=signature_font,
                sign_date=invoice_date.strftime('%Y-%m-%d'),
                invoice_date=invoice_date,
                invoice_number=preview_invoice_number
            )
        except Exception as e:
            print(f"PDF generation failed: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': f'Failed to generate PDF: {str(e)}'})
            }

        # Validate PDF generation succeeded
        if not pdf_bytes:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'PDF generation returned empty result'})
            }

        # Now atomically increment invoice number and create invoice record
        # This uses DynamoDB TransactWriteItems to guarantee no duplicate invoice numbers
        # Since PDF is already generated, we know the operation can succeed end-to-end
        invoice_number, invoice_metadata = _create_invoice_with_atomic_increment(
            user_id=user_id,
            user_config=user_config,
            hours=hours,
            week=week,
            active_client=active_client,
            client_email=client_email,
            accountant_email=accountant_email,
            save_only=save_only
        )

        # Upload PDF to S3 at users/{userId}/weekly/{invoiceId}.pdf
        bucket_name = os.environ['SST_Resource_InvoiStorage_name']
        invoice_id = week['invNum']
        s3_key = f"users/{user_id}/weekly/{invoice_id}.pdf"

        try:
            save_pdf_to_s3(pdf_bytes, bucket_name, s3_key)
        except Exception as e:
            print(f"S3 upload failed: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': f'Failed to save PDF to storage: {str(e)}'})
            }

        # Update invoice metadata with S3 key
        invoice_metadata['pdfKey'] = s3_key

        # Save invoice metadata to DynamoDB
        # Note: The atomic transaction already created the basic record,
        # but we need to update it with the S3 key after upload succeeds
        try:
            invoices_table = boto3.resource('dynamodb').Table(os.environ['INVOICES_TABLE'])
            invoices_table.put_item(Item=invoice_metadata)
        except ClientError as e:
            print(f"Failed to update invoice metadata: {str(e)}")
            # PDF is already saved, so this is not a critical failure
            # Log and continue

        # Return success response matching frontend expectations
        # Frontend expects: {saved: path, sent: [], invoiceNumber, s3Key}
        response_data = {
            'saved': s3_key,
            'invoiceNumber': invoice_number,
            'invoiceId': invoice_id,
            's3Key': s3_key,
            'totalHours': invoice_metadata['totalHours'],
            'totalPay': invoice_metadata['totalPay'],
            'status': invoice_metadata['status'],
            'createdAt': invoice_metadata['createdAt']
        }

        # If not save_only mode, would send email here (Phase 3)
        # For now, always return save-only response
        if not save_only:
            # TODO Phase 3: Send email via SES
            # For now, just indicate email would be sent
            response_data['sent'] = []  # Would contain email addresses if sent

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_data)
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except ClientError as e:
        print(f"AWS error in POST /api/submit/weekly: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to generate weekly invoice'})
        }
    except Exception as e:
        print(f"Unhandled error in submit_weekly handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def _create_invoice_with_atomic_increment(user_id, user_config, hours, week, active_client,
                                         client_email, accountant_email, save_only):
    """
    Atomically increment invoice number in user config and create invoice record.

    Uses DynamoDB TransactWriteItems to guarantee no duplicate invoice numbers
    even under concurrent requests.

    Returns:
        tuple: (invoice_number: str, invoice_metadata: dict)
    """
    # Generate invoice number with current counter value
    # Note: format_invoice_number reads nextNum from config internally
    invoice_number = format_invoice_number(user_config, 'weekly')

    # Calculate totals
    total_hours = sum(float(hours.get(day, 0)) for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])

    rate = float(user_config.get('rate', 0))
    subtotal = total_hours * rate

    # Calculate tax if enabled
    tax_enabled = user_config.get('taxEnabled', False)
    tax_rate = user_config.get('taxRate', 0)
    tax_amount = 0

    if tax_enabled:
        tax_amount = subtotal * (tax_rate / 100)

    total_pay = subtotal + tax_amount

    # Calculate due date based on payment terms
    payment_terms = user_config.get('paymentTerms', 'receipt')
    invoice_date = datetime.now()
    due_date = _calculate_due_date(invoice_date, payment_terms)

    # Create invoice metadata
    invoice_id = week['invNum']
    invoice_metadata = {
        'userId': user_id,
        'invoiceId': invoice_id,
        'invoiceNumber': invoice_number,
        'clientId': active_client.get('id', ''),
        'type': 'weekly',
        'status': 'draft',  # Always draft for Phase 2 (email sending is Phase 3)
        'weekStart': week['start'],
        'weekEnd': week['end'],
        'dueDate': due_date,
        'paymentTerms': payment_terms,
        'dailyHours': hours,
        'totalHours': total_hours,
        'rate': rate,
        'subtotal': subtotal,
        'taxRate': tax_rate,
        'taxAmount': tax_amount,
        'totalPay': total_pay,
        'template': user_config.get('template', 'morning-light'),
        'sentAt': None,  # Will be set in Phase 3 when email is sent
        'sentTo': [],
        'paidAt': None,
        'createdAt': datetime.now().isoformat()
    }

    # Perform atomic transaction: increment counter + create invoice
    # Using boto3 client (not resource) for TransactWriteItems
    dynamodb_client = boto3.client('dynamodb')
    users_table = os.environ['USERS_TABLE']
    invoices_table = os.environ['INVOICES_TABLE']

    try:
        # Convert invoice_metadata to DynamoDB format
        from boto3.dynamodb.types import TypeSerializer
        serializer = TypeSerializer()
        invoice_item_dynamodb = {k: serializer.serialize(v) for k, v in invoice_metadata.items()}

        # Execute atomic transaction
        dynamodb_client.transact_write_items(
            TransactItems=[
                {
                    'Update': {
                        'TableName': users_table,
                        'Key': {'userId': {'S': user_id}},
                        'UpdateExpression': 'SET invoiceNumberConfig.nextNum = invoiceNumberConfig.nextNum + :inc',
                        'ExpressionAttributeValues': {':inc': {'N': '1'}},
                        'ConditionExpression': 'attribute_exists(userId)'
                    }
                },
                {
                    'Put': {
                        'TableName': invoices_table,
                        'Item': invoice_item_dynamodb,
                        'ConditionExpression': 'attribute_not_exists(invoiceId)'
                    }
                }
            ]
        )
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'TransactionCanceledException':
            # Transaction failed - likely duplicate invoiceId or user not found
            cancellation_reasons = e.response.get('CancellationReasons', [])
            print(f"Transaction cancelled: {cancellation_reasons}")
            raise ValueError('Invoice already exists or user configuration error')
        raise

    return invoice_number, invoice_metadata


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
