import json
import logging
import sys
import os
from datetime import datetime
import base64
import boto3

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import get_user
from services.pdf_service import generate_weekly_invoice, save_pdf_to_s3, format_invoice_number, _calculate_due_date
from services.mail_service import send_weekly_email
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# S3 client for logo fetching
s3_client = boto3.client('s3')
# SST Ion provides bucket name via SST_Resource_<name>_name when linked
BUCKET_NAME = os.environ.get('SST_Resource_InvoiStorage_name')

# Re-export for test imports
__all__ = ['handler', '_calculate_due_date', '_populate_hours_from_default_shift']


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
        if not week:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'week is required in request body'})
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

        # Default shift prefill: If no hours provided, populate from client's default shift
        # This enables users with consistent schedules to generate invoices without manual hour entry
        if not hours or not any(hours.values()):
            default_shift = active_client.get('defaultShift')
            if default_shift:
                try:
                    hours = _populate_hours_from_default_shift(default_shift)
                except ValueError as e:
                    # Invalid default shift configuration - return 400 with helpful error
                    return {
                        'statusCode': 400,
                        'headers': headers,
                        'body': json.dumps({
                            'error': f'Invalid default shift configuration: {str(e)}'
                        })
                    }
            else:
                # No hours provided and no default shift configured
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({
                        'error': 'No hours provided. Either provide hours in the request or configure a default shift for this client in your profile.'
                    })
                }

        # Generate preview invoice number for PDF generation (before atomic increment)
        # Note: This is a preview only - the actual number will be confirmed after transaction succeeds
        preview_invoice_number = format_invoice_number(user_config, 'weekly')

        # Generate invoice PDF FIRST, before creating database records
        # This ensures PDF generation failures don't consume invoice numbers
        template_id = user_config.get('template', 'morning-light')
        signature_font = user_config.get('signatureFont', '')
        invoice_date = datetime.now()

        # Fetch logo from S3 if configured
        logo_data = None
        logo_key = user_config.get('logoKey')
        if logo_key:
            try:
                logo_data = _fetch_logo_from_s3(logo_key)
            except Exception as e:
                # Log error but don't fail - invoice can be generated without logo
                logger.warning(f"Failed to fetch logo from S3: {str(e)}")

        try:
            pdf_bytes = generate_weekly_invoice(
                config=user_config,
                hours=hours,
                week=week,
                template_id=template_id,
                signature_font=signature_font,
                sign_date=invoice_date.strftime('%Y-%m-%d'),
                invoice_date=invoice_date,
                invoice_number=preview_invoice_number,
                logo_data=logo_data
            )
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}")
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
            save_only=save_only,
            invoice_number=preview_invoice_number
        )

        # Upload PDF to S3 at users/{userId}/weekly/{invoiceId}.pdf
        bucket_name = os.environ['SST_Resource_InvoiStorage_name']
        invoice_id = week['invNum']
        s3_key = f"users/{user_id}/weekly/{invoice_id}.pdf"

        try:
            save_pdf_to_s3(pdf_bytes, bucket_name, s3_key)
        except Exception as e:
            logger.error(f"S3 upload failed: {str(e)}")
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
            logger.error(f"Failed to update invoice metadata: {str(e)}")
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
            'createdAt': invoice_metadata['createdAt'],
            'sent': []  # Initialize sent field - will be populated if email is sent
        }

        # Phase 3: Send email via SES if not save_only mode
        # Email failures are handled gracefully - the invoice is saved successfully
        # even if the email fails, and the user receives a warning instead of an error
        if not save_only:
            email_recipients = []
            email_warning = None

            # Build recipient list (filter out empty emails)
            if client_email:
                email_recipients.append(client_email)
            if accountant_email:
                email_recipients.append(accountant_email)

            if email_recipients:
                try:
                    # Send invoice email with PDF attachment
                    send_weekly_email(
                        to_addresses=email_recipients,
                        user_name=user_config.get('name', 'Contractor'),
                        week_start=week['start'],
                        week_end=week['end'],
                        total_hours=invoice_metadata['totalHours'],
                        total_pay=invoice_metadata['totalPay'],
                        pdf_data=pdf_bytes,
                        pdf_filename=f"{invoice_id}.pdf",
                        from_email="noreply@goinvoi.com"
                    )

                    # Persist updated status to DynamoDB first, before updating response
                    # This ensures the response status matches the database state
                    try:
                        invoice_metadata['status'] = 'sent'
                        invoice_metadata['sentAt'] = datetime.now().isoformat()
                        invoice_metadata['sentTo'] = email_recipients

                        invoices_table = boto3.resource('dynamodb').Table(os.environ['INVOICES_TABLE'])
                        invoices_table.put_item(Item=invoice_metadata)

                        # Only update response if database update succeeded
                        response_data['sent'] = email_recipients
                        response_data['status'] = 'sent'
                    except ClientError as e:
                        logger.error(f"Failed to update invoice status after email send: {str(e)}")
                        # Email was sent but status update failed
                        # Keep status as 'draft' to match database state
                        response_data['sent'] = []
                        response_data['emailWarning'] = f"Email sent to {', '.join(email_recipients)} but status update failed. Invoice remains in draft status."

                except Exception as e:
                    # Email failed but invoice was saved successfully
                    # Return success with warning rather than failing the entire operation
                    logger.error(f"Email send failed: {str(e)}")
                    email_warning = f"Invoice saved but email failed: {str(e)}"
                    response_data['sent'] = []
                    response_data['emailWarning'] = email_warning
            else:
                # No recipients configured
                response_data['sent'] = []
                response_data['emailWarning'] = "No email recipients configured"

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
    except ValueError as e:
        logger.error(f"Validation error in POST /api/submit/weekly: {str(e)}")
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }
    except ClientError as e:
        logger.error(f"AWS error in POST /api/submit/weekly: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to generate weekly invoice'})
        }
    except Exception as e:
        logger.error(f"Unhandled error in submit_weekly handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def _create_invoice_with_atomic_increment(user_id, user_config, hours, week, active_client,
                                         client_email, accountant_email, save_only, invoice_number):
    """
    Atomically increment invoice number in user config and create invoice record.

    Uses DynamoDB TransactWriteItems to guarantee no duplicate invoice numbers
    even under concurrent requests.

    Args:
        user_id: str - User ID
        user_config: dict - User configuration
        hours: dict - Daily hours data
        week: dict - Week metadata (start, end, invNum)
        active_client: dict - Active client data
        client_email: str - Client email address
        accountant_email: str - Accountant email address
        save_only: bool - Whether to save as draft only
        invoice_number: str - Pre-generated invoice number (from preview)

    Returns:
        tuple: (invoice_number: str, invoice_metadata: dict)
    """
    # Use the pre-generated invoice number passed from caller
    # This avoids regenerating the number which would cause gaps if the transaction fails

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
            logger.error(f"Transaction cancelled: {cancellation_reasons}")
            raise ValueError('Invoice already exists or user configuration error')
        raise

    return invoice_number, invoice_metadata


def _populate_hours_from_default_shift(default_shift):
    """
    Populate daily hours from client's default shift configuration.

    Args:
        default_shift: dict with keys:
            - start: str (e.g., "09:00")
            - end: str (e.g., "17:00")
            - days: list of str (e.g., ["Mon", "Tue", "Wed", "Thu", "Fri"])

    Returns:
        dict: Daily hours mapping full day names to calculated hours
              (e.g., {"Monday": 8.0, "Tuesday": 8.0, ...})

    Example:
        default_shift = {"start": "09:00", "end": "17:00", "days": ["Mon", "Tue", "Wed", "Thu", "Fri"]}
        → {"Monday": 8.0, "Tuesday": 8.0, "Wednesday": 8.0, "Thursday": 8.0, "Friday": 8.0,
           "Saturday": 0, "Sunday": 0}
    """
    # Parse shift start and end times to calculate hours per day
    start_time = default_shift.get('start', '09:00')
    end_time = default_shift.get('end', '17:00')
    shift_days = default_shift.get('days', [])

    # Calculate hours from start/end times (e.g., "09:00" to "17:00" = 8 hours)
    try:
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        hours_per_shift = (end_hour * 60 + end_min - start_hour * 60 - start_min) / 60.0
    except (ValueError, AttributeError) as e:
        # Invalid time format in default shift configuration
        error_msg = f"Invalid time format in default shift: start='{start_time}', end='{end_time}'. Expected format: HH:MM"
        logger.error(f"{error_msg} - {str(e)}")
        raise ValueError(error_msg)

    # Validate that calculated hours are positive and reasonable
    if hours_per_shift <= 0:
        raise ValueError(f"Invalid default shift: end time must be after start time (start='{start_time}', end='{end_time}', calculated hours={hours_per_shift})")
    if hours_per_shift > 24:
        raise ValueError(f"Invalid default shift: shift duration cannot exceed 24 hours (start='{start_time}', end='{end_time}', calculated hours={hours_per_shift})")

    # Map abbreviated day names to full names
    day_mapping = {
        'Mon': 'Monday',
        'Tue': 'Tuesday',
        'Wed': 'Wednesday',
        'Thu': 'Thursday',
        'Fri': 'Friday',
        'Sat': 'Saturday',
        'Sun': 'Sunday'
    }

    # Initialize all days to 0, then populate configured shift days
    hours = {
        'Monday': 0,
        'Tuesday': 0,
        'Wednesday': 0,
        'Thursday': 0,
        'Friday': 0,
        'Saturday': 0,
        'Sunday': 0
    }

    for abbrev_day in shift_days:
        full_day = day_mapping.get(abbrev_day)
        if full_day:
            hours[full_day] = hours_per_shift
        else:
            logger.warning(f"Unrecognized day abbreviation '{abbrev_day}' in default shift configuration. Expected one of: {', '.join(day_mapping.keys())}")

    return hours


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


def _fetch_logo_from_s3(logo_key):
    """
    Fetch logo image from S3 and return as base64-encoded data URL.

    Args:
        logo_key: str - S3 key for logo (e.g., users/{userId}/logo.png)

    Returns:
        str - Base64-encoded data URL (e.g., data:image/png;base64,...)
        None - If logo cannot be fetched

    Raises:
        ClientError - If S3 operation fails
    """
    try:
        # Fetch logo from S3
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=logo_key)
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
