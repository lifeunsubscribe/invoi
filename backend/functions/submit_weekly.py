import json
import logging
import sys
import os
from datetime import datetime
from decimal import Decimal
import boto3

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import get_user, put_invoice
from services.pdf_service import generate_weekly_invoice, save_pdf_to_s3, format_invoice_number, _calculate_due_date
from services.mail_service import send_weekly_email
from services.logging_config import setup_logging
from services.s3_service import fetch_logo_from_s3
from botocore.exceptions import ClientError

# Configure logging for this Lambda function
setup_logging()
logger = logging.getLogger(__name__)

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

    Note: CORS is handled by API Gateway (configured in sst.config.ts).
    Lambda functions should not set CORS headers.
    """
    # Response headers
    headers = {
        'Content-Type': 'application/json',
    }

    try:
        # Extract HTTP method (supports both API Gateway v1 and v2 formats)
        http_method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod', 'POST')

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

        # Atomically increment invoice counter BEFORE PDF generation
        # This prevents race conditions where concurrent requests could generate PDFs
        # with the same number but different database numbers
        next_counter_value = _increment_invoice_counter(user_id)

        # Update user_config with the new counter value for invoice number formatting
        user_config['invoiceNumberConfig']['nextNum'] = next_counter_value

        # Generate the invoice number using the atomically-incremented counter
        # This is the FINAL number that will be used in both PDF and database
        invoice_number = format_invoice_number(user_config, 'weekly')

        # Generate invoice PDF with the final invoice number
        # Note: If PDF generation fails, the counter is already incremented (creates a gap),
        # but this is preferable to race conditions causing mismatched numbers
        template_id = user_config.get('template', 'morning-light')
        signature_font = user_config.get('signatureFont', '')
        invoice_date = datetime.now()

        # Fetch logo from S3 if configured
        logo_data = None
        logo_key = user_config.get('logoKey')
        if logo_key:
            try:
                logo_data = fetch_logo_from_s3(logo_key)
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
                invoice_number=invoice_number,
                logo_data=logo_data
            )
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}")
            logger.warning(f"Invoice number gap created: invoice number {invoice_number} was allocated but PDF generation failed for user {user_id}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': f'Failed to generate PDF: {str(e)}'})
            }

        # Validate PDF generation succeeded
        if not pdf_bytes:
            logger.warning(f"Invoice number gap created: invoice number {invoice_number} was allocated but PDF generation returned empty result for user {user_id}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'PDF generation returned empty result'})
            }

        # Create invoice database record
        # Note: Invoice number was already atomically incremented above, so this just creates the record
        try:
            invoice_metadata = _create_invoice_record(
                user_id=user_id,
                user_config=user_config,
                hours=hours,
                week=week,
                active_client=active_client,
                client_email=client_email,
                accountant_email=accountant_email,
                save_only=save_only,
                invoice_number=invoice_number
            )
        except ValueError as e:
            logger.error(f"Failed to create invoice record: {str(e)}")
            logger.warning(f"Invoice number gap created: invoice number {invoice_number} was allocated but invoice record creation failed for user {user_id}")
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': str(e)})
            }
        except ClientError as e:
            logger.error(f"Failed to create invoice record: {str(e)}")
            logger.warning(f"Invoice number gap created: invoice number {invoice_number} was allocated but invoice record creation failed for user {user_id}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Failed to create invoice record'})
            }

        # Upload PDF to S3 at users/{userId}/weekly/{invoiceId}.pdf
        bucket_name = os.environ['SST_Resource_InvoiStorage_name']
        invoice_id = week['invNum']
        s3_key = f"users/{user_id}/weekly/{invoice_id}.pdf"

        try:
            save_pdf_to_s3(pdf_bytes, bucket_name, s3_key)
        except Exception as e:
            logger.error(f"S3 upload failed: {str(e)}")
            logger.warning(f"Invoice number gap created: invoice number {invoice_number} was allocated but S3 upload failed for user {user_id}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': f'Failed to save PDF to storage: {str(e)}'})
            }

        # Update invoice metadata with S3 key
        invoice_metadata['pdfKey'] = s3_key

        # Phase 3: Send email via SES if not save_only mode
        # Email failures are handled gracefully - the invoice is saved successfully
        # even if the email fails, and the user receives a warning instead of an error
        email_warning = None
        if not save_only:
            email_recipients = []

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

                    # Update invoice metadata to reflect successful email send
                    invoice_metadata['status'] = 'sent'
                    invoice_metadata['sentAt'] = datetime.now().isoformat()
                    invoice_metadata['sentTo'] = email_recipients

                except Exception as e:
                    # Email failed but invoice was saved successfully
                    # Return success with warning rather than failing the entire operation
                    logger.error(f"Email send failed: {str(e)}")
                    email_warning = f"Invoice saved but email failed: {str(e)}"
            else:
                # No recipients configured
                email_warning = "No email recipients configured"

        # Save complete invoice metadata to DynamoDB (single write operation)
        # This replaces the double-write pattern that occurred when status was updated separately
        try:
            put_invoice(invoice_metadata)
        except ClientError as e:
            logger.error(f"Failed to save invoice metadata: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Failed to save invoice metadata to database'})
            }

        # Return success response matching frontend expectations
        # Frontend expects: {saved: path, sent: [], invoiceNumber, s3Key}
        # Convert Decimal values to float for JSON serialization
        response_data = {
            'saved': s3_key,
            'invoiceNumber': invoice_number,
            'invoiceId': invoice_id,
            's3Key': s3_key,
            'totalHours': float(invoice_metadata['totalHours']),
            'totalPay': float(invoice_metadata['totalPay']),
            'status': invoice_metadata['status'],
            'createdAt': invoice_metadata['createdAt'],
            'sent': invoice_metadata.get('sentTo', [])
        }

        # Add email warning if applicable
        if email_warning:
            response_data['emailWarning'] = email_warning

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


def _increment_invoice_counter(user_id):
    """
    Atomically increment the invoice counter and return the new value.

    This must happen BEFORE PDF generation to eliminate race conditions where
    concurrent requests could read the same counter value and generate PDFs with
    the same preview number but different final database numbers.

    Args:
        user_id: str - User ID

    Returns:
        int - The newly incremented counter value

    Raises:
        ClientError - If DynamoDB operation fails
        ValueError - If user not found or counter config missing
    """
    dynamodb_client = boto3.client('dynamodb')
    users_table = os.environ['USERS_TABLE']

    try:
        # Atomically increment counter and return the new value
        response = dynamodb_client.update_item(
            TableName=users_table,
            Key={'userId': {'S': user_id}},
            UpdateExpression='SET invoiceNumberConfig.nextNum = invoiceNumberConfig.nextNum + :inc',
            ExpressionAttributeValues={':inc': {'N': '1'}},
            ConditionExpression='attribute_exists(userId) AND attribute_exists(invoiceNumberConfig.nextNum)',
            ReturnValues='ALL_NEW'
        )

        # Extract the new counter value from the response
        updated_config = response['Attributes']['invoiceNumberConfig']['M']
        next_num = int(updated_config['nextNum']['N'])

        return next_num

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'ConditionalCheckFailedException':
            logger.error(f"User {user_id} not found or missing invoice counter configuration")
            raise ValueError('User configuration error: invoice counter not initialized')
        logger.error(f"Failed to increment invoice counter for user {user_id}: {str(e)}")
        raise


def _create_invoice_record(user_id, user_config, hours, week, active_client,
                           client_email, accountant_email, save_only, invoice_number):
    """
    Create invoice record in DynamoDB.

    Note: Invoice counter is already incremented before this function is called.
    This function only creates the invoice record.

    Args:
        user_id: str - User ID
        user_config: dict - User configuration
        hours: dict - Daily hours data
        week: dict - Week metadata (start, end, invNum)
        active_client: dict - Active client data
        client_email: str - Client email address
        accountant_email: str - Accountant email address
        save_only: bool - Whether to save as draft only
        invoice_number: str - Final invoice number (already incremented)

    Returns:
        dict - Invoice metadata
    """

    # Calculate totals
    # Use Decimal for DynamoDB compatibility
    total_hours = sum(Decimal(str(hours.get(day, 0))) for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])

    rate = Decimal(str(user_config.get('rate', 0)))
    subtotal = total_hours * rate

    # Calculate tax if enabled
    tax_enabled = user_config.get('taxEnabled', False)
    tax_rate = Decimal(str(user_config.get('taxRate', 0)))
    tax_amount = Decimal('0')

    if tax_enabled:
        tax_amount = subtotal * (tax_rate / Decimal('100'))

    total_pay = subtotal + tax_amount

    # Calculate due date based on payment terms
    payment_terms = user_config.get('paymentTerms', 'receipt')
    invoice_date = datetime.now()
    due_date = _calculate_due_date(invoice_date, payment_terms)

    # Create invoice metadata
    # Convert all numeric values to Decimal for DynamoDB compatibility
    invoice_id = week['invNum']
    # Convert dailyHours to Decimal for DynamoDB compatibility
    daily_hours_decimal = {day: Decimal(str(val)) for day, val in hours.items()}

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
        'dailyHours': daily_hours_decimal,
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

    # Create invoice record in DynamoDB
    # Note: Counter is already incremented, so no atomic transaction needed
    invoices_table = os.environ['INVOICES_TABLE']

    try:
        # Use DynamoDB resource for simpler put_item operation
        dynamodb_resource = boto3.resource('dynamodb')
        table = dynamodb_resource.Table(invoices_table)

        # Put item with condition to prevent duplicates
        table.put_item(
            Item=invoice_metadata,
            ConditionExpression='attribute_not_exists(invoiceId)'
        )
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'ConditionalCheckFailedException':
            # Invoice ID already exists
            logger.error(f"Invoice {invoice_metadata['invoiceId']} already exists")
            raise ValueError('Invoice already exists')
        logger.error(f"Failed to create invoice record: {str(e)}")
        raise

    return invoice_metadata


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
