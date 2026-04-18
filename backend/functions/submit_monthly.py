import json
import logging
import sys
import os
from datetime import datetime
import calendar
import base64
import boto3
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import query_invoices, get_user, get_invoice
from services.pdf_service import generate_monthly_report, save_pdf_to_s3
from services.mail_service import send_monthly_email
from services.logging_config import setup_logging
from botocore.exceptions import ClientError

# Configure logging for this Lambda function
setup_logging()
logger = logging.getLogger(__name__)

# S3 client for logo fetching
s3_client = boto3.client('s3')
# SST Ion provides bucket name via SST_Resource_<name>_name when linked
BUCKET_NAME = os.environ.get('SST_Resource_InvoiStorage_name')


def handler(event, context):
    """
    Lambda handler for POST /api/submit/monthly — aggregate weekly invoices and generate monthly report PDF.

    Request body (JSON):
        {
            "year": 2026,
            "month": 3,
            "send": true,  // Optional: if true, send email after PDF generation (default: true)
            "accountantEmail": "accountant@example.com"  // Optional: recipient for monthly report
        }

    Returns:
        200: Report metadata including S3 key
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

        year = body.get('year')
        month = body.get('month')
        send = body.get('send', True)  # Default to True for backward compatibility
        accountant_email = body.get('accountantEmail', '')

        # Validate required parameters
        if not year or not month:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Both year and month are required in request body'})
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

            # Validate that the month has already occurred (prevent future month submissions)
            now = datetime.now()
            requested_date = datetime(year_int, month_int, 1)
            if requested_date > datetime(now.year, now.month, 1):
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Cannot submit report for a future month'})
                }
        except ValueError:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Year and month must be valid integers'})
            }

        # Get user configuration
        user_config = get_user(user_id)
        if not user_config:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'User configuration not found'})
            }

        # Idempotency check: Check if report already exists for this month
        # Report ID format: RPT-{year}-{month}
        report_id = f"RPT-{year_int:04d}-{month_int:02d}"
        existing_report = get_invoice(user_id, report_id)

        if existing_report:
            # Validate that existing report has complete critical data
            # If report is corrupted or incomplete, regenerate it instead of returning partial data
            has_complete_data = all([
                existing_report.get('pdfKey'),
                existing_report.get('monthLabel'),
                existing_report.get('totalHours') is not None,
                existing_report.get('totalPay') is not None
            ])

            if has_complete_data:
                # Report already exists with complete data - return existing data (idempotent behavior)
                logger.info(f"Report {report_id} already exists for user {user_id}. Returning existing report.")
                return {
                    'statusCode': 200,
                    'headers': headers,
                    'body': json.dumps({
                        'reportId': existing_report.get('invoiceId'),
                        's3Key': existing_report.get('pdfKey'),
                        'monthLabel': existing_report.get('monthLabel'),
                        'totalHours': existing_report.get('totalHours'),
                        'totalPay': existing_report.get('totalPay'),
                        'weekCount': existing_report.get('weekCount'),
                        'status': existing_report.get('status'),
                        'createdAt': existing_report.get('createdAt'),
                        'alreadyExists': True  # Flag to indicate this was an idempotent response
                    })
                }
            else:
                # Existing report is incomplete or corrupted - regenerate it
                logger.warning(f"Report {report_id} exists but is incomplete. Regenerating report.")
                # Continue to regeneration logic below

        # Query weekly invoices for this month using scan-month logic
        # Format: INV-YYYYMMDD (e.g., INV-20260301 to INV-20260331)
        # Using day 01-31 covers all possible dates in any month
        invoice_id_start = f"INV-{year_int:04d}{month_int:02d}01"
        invoice_id_end = f"INV-{year_int:04d}{month_int:02d}31"

        weekly_invoices = query_invoices(
            user_id,
            filters={
                'invoiceId_start': invoice_id_start,
                'invoiceId_end': invoice_id_end,
                'type': 'weekly'  # Only weekly invoices (exclude monthly reports)
            }
        )

        # Transform weekly invoices into week_data format for PDF generation
        # week_data format: list of dicts with 'label' (str) and 'hours' (int)
        week_data = []
        for invoice in weekly_invoices:
            week_label = f"{invoice.get('weekStart', '')} – {invoice.get('weekEnd', '')}"
            total_hours = invoice.get('totalHours', 0)
            week_data.append({
                'label': week_label,
                'hours': total_hours
            })

        # Validate that there is data to report
        if not week_data:
            month_name = calendar.month_name[month_int]
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': f'No weekly invoices found for {month_name} {year_int}. Cannot generate empty report.'
                })
            }

        # Generate month label (e.g., "March 2026")
        month_name = calendar.month_name[month_int]
        month_label = f"{month_name} {year_int}"

        # Fetch logo from S3 if configured
        logo_data = None
        logo_key = user_config.get('logoKey')
        if logo_key:
            try:
                logo_data = _fetch_logo_from_s3(logo_key)
            except Exception as e:
                # Log error but don't fail - report can be generated without logo
                logger.warning(f"Failed to fetch logo from S3: {str(e)}")

        # Generate monthly report PDF
        # Uses user's template, rate, and other config from user_config
        pdf_bytes = generate_monthly_report(
            config=user_config,
            week_data=week_data,
            month_label=month_label,
            template_id=user_config.get('template', 'caring-hands'),
            signature_font=user_config.get('signatureFont', ''),
            sign_date=datetime.now().strftime('%Y-%m-%d'),
            invoice_date=datetime.now(),
            logo_data=logo_data
        )

        # Validate PDF generation succeeded
        if not pdf_bytes:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Failed to generate PDF report'})
            }

        # Upload PDF to S3 at users/{userId}/reports/RPT-{year}-{month}.pdf
        # SST Ion provides bucket name via SST_Resource_<name>_name when linked
        bucket_name = os.environ['SST_Resource_InvoiStorage_name']
        # Note: report_id already defined above during idempotency check
        s3_key = f"users/{user_id}/reports/{report_id}.pdf"

        save_pdf_to_s3(pdf_bytes, bucket_name, s3_key)

        # Calculate totals for metadata
        total_hours = sum(w['hours'] for w in week_data)

        # Safely coerce rate to float with validation
        try:
            rate = float(user_config.get('rate', 0))
            if rate < 0:
                return {
                    'statusCode': 500,
                    'headers': headers,
                    'body': json.dumps({'error': 'Invalid user configuration: rate must be non-negative'})
                }
        except (ValueError, TypeError):
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid user configuration: rate must be a valid number'})
            }

        total_pay = total_hours * rate

        # Save report metadata to Invoices table with type="monthly"
        # Convert numeric values to Decimal for DynamoDB compatibility
        report_metadata = {
            'userId': user_id,
            'invoiceId': report_id,
            'type': 'monthly',
            'status': 'draft',  # Initial status (will be updated to 'sent' if email succeeds)
            'year': year_int,
            'month': month_int,
            'monthLabel': month_label,
            'weekCount': len(week_data),
            'totalHours': Decimal(str(total_hours)),
            'rate': Decimal(str(rate)),
            'totalPay': Decimal(str(total_pay)),
            'pdfKey': s3_key,
            'sentAt': None,
            'sentTo': [],
            'createdAt': datetime.now().isoformat()
        }

        # Save report metadata to DynamoDB using direct DynamoDB access
        try:
            invoices_table = boto3.resource('dynamodb').Table(os.environ['INVOICES_TABLE'])
            invoices_table.put_item(Item=report_metadata)
        except ClientError as e:
            logger.error(f"Failed to save report metadata: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Failed to save report metadata'})
            }

        # Prepare response data
        # Convert Decimal values back to float for JSON serialization
        response_data = {
            'reportId': report_id,
            's3Key': s3_key,
            'monthLabel': month_label,
            'totalHours': float(report_metadata['totalHours']),
            'totalPay': float(report_metadata['totalPay']),
            'weekCount': len(week_data),
            'status': report_metadata['status'],
            'createdAt': report_metadata['createdAt']
        }

        # Phase 3: Send email via SES if send=True
        # Email failures are handled gracefully - the report is saved successfully
        # even if the email fails, and the user receives a warning instead of an error
        if send:
            email_recipients = []
            email_warning = None

            # Build recipient list (only accountant for monthly reports)
            if accountant_email:
                email_recipients.append(accountant_email)

            if email_recipients:
                try:
                    # Send monthly report email with PDF attachment
                    send_monthly_email(
                        to_addresses=email_recipients,
                        user_name=user_config.get('name', 'Contractor'),
                        month_label=month_label,
                        total_hours=total_hours,
                        total_pay=total_pay,
                        pdf_data=pdf_bytes,
                        pdf_filename=f"{report_id}.pdf",
                        from_email="noreply@goinvoi.com"
                    )

                    # Persist updated status to DynamoDB first, before updating response
                    # This ensures the response status matches the database state
                    try:
                        report_metadata['status'] = 'sent'
                        report_metadata['sentAt'] = datetime.now().isoformat()
                        report_metadata['sentTo'] = email_recipients

                        invoices_table = boto3.resource('dynamodb').Table(os.environ['INVOICES_TABLE'])
                        invoices_table.put_item(Item=report_metadata)

                        # Only update response if database update succeeded
                        response_data['sent'] = email_recipients
                        response_data['status'] = 'sent'
                    except ClientError as e:
                        logger.error(f"Failed to update report status after email send: {str(e)}")
                        # Email was sent but status update failed
                        # Keep status as 'draft' to match database state
                        response_data['sent'] = []
                        response_data['emailWarning'] = f"Email sent to {', '.join(email_recipients)} but status update failed. Report remains in draft status."

                except Exception as e:
                    # Email failed but report was saved successfully
                    # Return success with warning rather than failing the entire operation
                    logger.error(f"Email send failed: {str(e)}")
                    email_warning = f"Report saved but email failed: {str(e)}"
                    response_data['sent'] = []
                    response_data['emailWarning'] = email_warning
            else:
                # No recipients configured
                response_data['sent'] = []
                response_data['emailWarning'] = "No email recipient configured"
        else:
            # Send=False, just save as draft
            response_data['sent'] = []

        # Return report metadata including S3 key
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
        logger.error(f"AWS error in POST /api/submit/monthly: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to generate monthly report'})
        }
    except Exception as e:
        logger.error(f"Unhandled error in submit_monthly handler: {str(e)}")
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
