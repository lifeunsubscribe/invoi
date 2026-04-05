import json
import logging
import sys
import os
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import get_invoice, get_user
from services.mail_service import send_email
from services.logging_config import setup_logging

# Configure logging for this Lambda function
setup_logging()
logger = logging.getLogger(__name__)

# S3 client for fetching PDFs
s3_client = boto3.client('s3')


def handler(event, context):
    """
    Lambda handler for POST /api/invoices/resend — resend invoices to clients.

    Request body (JSON):
        {
            "invoiceIds": ["INV-001", "INV-002", ...]
        }

    Returns:
        200: Success with counts of successful/failed resends
        400: Invalid request parameters
        401: Missing or invalid authorization
        404: One or more invoices not found or not owned by user
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
        # Extract HTTP method
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

        invoice_ids = body.get('invoiceIds', [])

        # Validate request parameters
        if not invoice_ids or not isinstance(invoice_ids, list):
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'invoiceIds must be a non-empty array'})
            }

        # Limit number of invoices to prevent resource exhaustion
        MAX_INVOICE_COUNT = 50
        if len(invoice_ids) > MAX_INVOICE_COUNT:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': f'Cannot resend more than {MAX_INVOICE_COUNT} invoices at once'})
            }

        # Get user configuration for sender email
        user_config = get_user(user_id)
        if not user_config:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'User configuration not found'})
            }

        # Get bucket name from environment
        bucket_name = os.environ.get('InvoiStorage') or os.environ.get('SST_Resource_InvoiStorage_name')
        if not bucket_name:
            logger.error("InvoiStorage bucket name not found in environment")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Storage configuration error'})
            }

        # Process each invoice
        successful = 0
        failed = 0
        failed_details = []

        for invoice_id in invoice_ids:
            try:
                # Fetch invoice metadata
                invoice = get_invoice(user_id, invoice_id)

                # Verify ownership and existence
                if not invoice or invoice.get('userId') != user_id:
                    failed += 1
                    failed_details.append(f'{invoice_id}: Not found or access denied')
                    continue

                # Skip draft invoices (never sent before)
                if invoice.get('status') == 'draft':
                    failed += 1
                    failed_details.append(f'{invoice_id}: Cannot resend draft invoice')
                    continue

                # Determine recipients
                recipients = []

                # Get client email from user's clients list
                client_id = invoice.get('clientId')
                if client_id and user_config.get('clients'):
                    client = next((c for c in user_config['clients'] if c.get('id') == client_id), None)
                    if client and client.get('email'):
                        recipients.append(client['email'])

                # Add accountant email if configured
                if user_config.get('accountantEmail'):
                    recipients.append(user_config['accountantEmail'])

                if not recipients:
                    failed += 1
                    failed_details.append(f'{invoice_id}: No recipient email configured')
                    continue

                # Fetch PDF from S3
                pdf_key = invoice.get('pdfKey')
                if not pdf_key:
                    failed += 1
                    failed_details.append(f'{invoice_id}: PDF not found')
                    continue

                try:
                    pdf_obj = s3_client.get_object(Bucket=bucket_name, Key=pdf_key)
                    pdf_data = pdf_obj['Body'].read()
                except ClientError as e:
                    failed += 1
                    failed_details.append(f'{invoice_id}: Failed to fetch PDF')
                    logger.error(f"S3 error fetching {pdf_key}: {str(e)}")
                    continue

                # Generate email subject and body
                invoice_number = invoice.get('invoiceNumber', invoice_id)
                week_start = invoice.get('weekStart', '')
                week_end = invoice.get('weekEnd', '')
                invoice_type = invoice.get('type', 'weekly')

                if invoice_type == 'weekly':
                    subject = f'Invoice {invoice_number} - Week of {week_start}'
                    body = _create_resend_email_body(
                        user_config.get('name', 'Contractor'),
                        week_start,
                        week_end,
                        invoice.get('totalHours', 0),
                        invoice.get('totalPay', 0)
                    )
                else:  # monthly
                    month_label = invoice.get('monthLabel', '')
                    subject = f'Monthly Report {invoice_number} - {month_label}'
                    body = _create_monthly_resend_email_body(
                        user_config.get('name', 'Contractor'),
                        month_label,
                        invoice.get('totalHours', 0),
                        invoice.get('totalPay', 0)
                    )

                # Send email
                pdf_filename = f'{invoice_number}.pdf'

                send_email(
                    to_addresses=recipients,
                    subject=subject,
                    body_text=body,
                    attachments=[{
                        'filename': pdf_filename,
                        'data': pdf_data
                    }],
                    from_email='noreply@goinvoi.com'
                )

                successful += 1

            except Exception as e:
                failed += 1
                failed_details.append(f'{invoice_id}: {str(e)}')
                logger.error(f"Error resending invoice {invoice_id}: {str(e)}")

        # Return summary
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'successful': successful,
                'failed': failed,
                'total': len(invoice_ids),
                'failedDetails': failed_details if failed_details else None
            })
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except Exception as e:
        logger.error(f"Unhandled error in resend handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def _create_resend_email_body(name, week_start, week_end, total_hours, total_pay):
    """
    Generate plain text email body for resending weekly invoice.

    Note: Includes "(Resent)" marker to distinguish from original send.
    """
    return f"""Hello,

(Resent) Please find attached the invoice for {name} for the week of {week_start} through {week_end}.

Total Hours: {total_hours}
Total Amount Due: ${total_pay:.2f}

If you have already processed this invoice, please disregard this message.

Thank you,
{name}

---
Sent via Invoi (goinvoi.com)
"""


def _create_monthly_resend_email_body(name, month_label, total_hours, total_pay):
    """
    Generate plain text email body for resending monthly report.

    Note: Includes "(Resent)" marker to distinguish from original send.
    """
    return f"""Hello,

(Resent) Please find attached the monthly report for {name} for {month_label}.

Total Hours: {total_hours}
Total Amount Due: ${total_pay:.2f}

If you have already processed this report, please disregard this message.

Thank you,
{name}

---
Sent via Invoi (goinvoi.com)
"""


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
