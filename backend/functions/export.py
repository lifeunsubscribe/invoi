import json
import logging
import sys
import os
import csv
import io
import zipfile
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import get_invoice

logger = logging.getLogger(__name__)

# Initialize AWS clients
s3_client = boto3.client('s3')


def handler(event, context):
    """
    Lambda handler for POST /api/export — generate ZIP or CSV of selected invoices.

    Request body (JSON):
        {
            "invoiceIds": ["INV-001", "INV-002", ...],
            "format": "zip" or "csv"
        }

    Returns:
        200: Signed S3 URL to download the generated export file
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
        export_format = body.get('format', '').lower()

        # Validate request parameters
        if not invoice_ids or not isinstance(invoice_ids, list):
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'invoiceIds must be a non-empty array'})
            }

        # Limit number of invoices to prevent resource exhaustion
        MAX_INVOICE_COUNT = 100
        if len(invoice_ids) > MAX_INVOICE_COUNT:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': f'Cannot export more than {MAX_INVOICE_COUNT} invoices at once'})
            }

        if export_format not in ['zip', 'csv']:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'format must be "zip" or "csv"'})
            }

        # Fetch all invoices and validate ownership
        invoices = []
        for invoice_id in invoice_ids:
            invoice = get_invoice(user_id, invoice_id)

            # Return 404 for non-existent or unauthorized invoices
            if not invoice or invoice.get('userId') != user_id:
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({'error': f'Invoice {invoice_id} not found or access denied'})
                }

            invoices.append(invoice)

        # Generate export based on format
        if export_format == 'csv':
            return _handle_csv_export(user_id, invoices, headers)
        else:  # zip
            return _handle_zip_export(user_id, invoices, headers)

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except Exception as e:
        logger.error(f"Unhandled error in export handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def _handle_csv_export(user_id, invoices, headers):
    """
    Generate CSV export of invoice data.

    CSV columns: invoiceId, date, client, hours, amount, status
    """
    try:
        # Create CSV in memory
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)

        # Write header row
        csv_writer.writerow(['Invoice ID', 'Date', 'Client', 'Hours', 'Amount', 'Status'])

        # Write data rows
        for invoice in invoices:
            # Extract date from invoiceId or weekStart/weekEnd
            invoice_date = invoice.get('weekStart') or invoice.get('weekEnd') or invoice.get('createdAt', '')
            if invoice_date:
                # Parse ISO date and format as YYYY-MM-DD
                try:
                    date_obj = datetime.fromisoformat(invoice_date.replace('Z', '+00:00'))
                    invoice_date = date_obj.strftime('%Y-%m-%d')
                except (ValueError, AttributeError):
                    # Keep as-is if parsing fails
                    pass

            # Get client ID or name
            client = invoice.get('clientId', '')

            # Get hours
            total_hours = invoice.get('totalHours', 0)

            # Get amount (convert Decimal to float for CSV)
            total_pay = invoice.get('totalPay', 0)
            if isinstance(total_pay, Decimal):
                total_pay = float(total_pay)

            # Get status
            status = invoice.get('status', 'unknown')

            csv_writer.writerow([
                invoice.get('invoiceId', ''),
                invoice_date,
                client,
                total_hours,
                f"{total_pay:.2f}",
                status
            ])

        # Get CSV content as bytes
        csv_content = csv_buffer.getvalue().encode('utf-8')
        csv_buffer.close()

        # Upload to S3
        bucket_name = os.environ.get('InvoiStorage')
        if not bucket_name:
            logger.error("Error: InvoiStorage bucket name not found in environment")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Storage configuration error'})
            }

        # Generate unique filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        s3_key = f"users/{user_id}/exports/export-{timestamp}.csv"

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=csv_content,
            ContentType='text/csv',
            ContentDisposition=f'attachment; filename="invoices-{timestamp}.csv"'
        )

        # Generate signed URL (valid for 1 hour)
        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': s3_key
            },
            ExpiresIn=3600  # 1 hour
        )

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'format': 'csv',
                'downloadUrl': signed_url,
                'expiresIn': 3600,
                'invoiceCount': len(invoices)
            })
        }

    except ClientError as e:
        logger.error(f"S3 error in CSV export: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to generate CSV export'})
        }
    except Exception as e:
        logger.error(f"Error in CSV export handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def _handle_zip_export(user_id, invoices, headers):
    """
    Generate ZIP export containing PDF files for selected invoices.

    Includes: invoice PDFs, log PDFs (if available), monthly report PDFs (if available)

    Implementation note: Uses in-memory ZIP creation to avoid Lambda filesystem limits.
    For very large exports (100+ invoices), consider implementing async processing
    with progress tokens to avoid Lambda timeout.
    """
    try:
        bucket_name = os.environ.get('InvoiStorage')
        if not bucket_name:
            logger.error("Error: InvoiStorage bucket name not found in environment")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': 'Storage configuration error'})
            }

        # Create ZIP in memory (avoids Lambda /tmp filesystem quota)
        zip_buffer = io.BytesIO()

        # Track failures to inform user
        failed_pdfs = []

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            pdf_count = 0

            for invoice in invoices:
                invoice_id = invoice.get('invoiceId', 'unknown')

                # Add invoice PDF if available
                pdf_key = invoice.get('pdfKey')
                if pdf_key:
                    try:
                        pdf_obj = s3_client.get_object(Bucket=bucket_name, Key=pdf_key)
                        pdf_data = pdf_obj['Body'].read()

                        # Use invoice ID as filename for clarity
                        filename = f"{invoice_id}.pdf"
                        zip_file.writestr(filename, pdf_data)
                        pdf_count += 1
                    except ClientError as e:
                        error_msg = f"Invoice PDF for {invoice_id}"
                        logger.warning(f"Warning: Could not fetch PDF for {invoice_id}: {str(e)}")
                        failed_pdfs.append(error_msg)

                # Add log PDF if available
                log_pdf_key = invoice.get('logPdfKey')
                if log_pdf_key:
                    try:
                        log_pdf_obj = s3_client.get_object(Bucket=bucket_name, Key=log_pdf_key)
                        log_pdf_data = log_pdf_obj['Body'].read()

                        filename = f"{invoice_id}-log.pdf"
                        zip_file.writestr(filename, log_pdf_data)
                        pdf_count += 1
                    except ClientError as e:
                        error_msg = f"Log PDF for {invoice_id}"
                        logger.warning(f"Warning: Could not fetch log PDF for {invoice_id}: {str(e)}")
                        failed_pdfs.append(error_msg)

        # Check if we successfully added any PDFs
        if pdf_count == 0:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'No PDFs available for selected invoices'})
            }

        # Get ZIP content as bytes
        zip_buffer.seek(0)
        zip_content = zip_buffer.read()
        zip_buffer.close()

        # Generate unique filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        s3_key = f"users/{user_id}/exports/export-{timestamp}.zip"

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=zip_content,
            ContentType='application/zip',
            ContentDisposition=f'attachment; filename="invoices-{timestamp}.zip"'
        )

        # Generate signed URL (valid for 1 hour)
        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': s3_key
            },
            ExpiresIn=3600  # 1 hour
        )

        response_body = {
            'format': 'zip',
            'downloadUrl': signed_url,
            'expiresIn': 3600,
            'invoiceCount': len(invoices),
            'pdfCount': pdf_count
        }

        # Include failure information if any PDFs failed to fetch
        if failed_pdfs:
            response_body['warnings'] = {
                'failedPdfs': failed_pdfs,
                'message': f'{len(failed_pdfs)} PDF(s) could not be included in the export'
            }

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_body)
        }

    except ClientError as e:
        logger.error(f"S3 error in ZIP export: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to generate ZIP export'})
        }
    except Exception as e:
        logger.error(f"Error in ZIP export handler: {str(e)}")
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
