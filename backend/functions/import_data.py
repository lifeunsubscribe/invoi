import json
import logging
import sys
import os
import base64
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import get_user, put_invoice

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# S3 client for PDF storage
s3_client = boto3.client('s3')

# Get bucket name from SST Resource environment variable
BUCKET_NAME = os.environ.get('SST_Resource_InvoiStorage_name')

# Maximum file size (10MB per file)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# PDF magic byte signature
PDF_SIGNATURE = b'%PDF'


def _validate_pdf_magic_bytes(pdf_bytes):
    """
    Validate that file bytes are actually a PDF by checking magic bytes.
    Returns True if valid PDF, False otherwise.
    """
    if not pdf_bytes or len(pdf_bytes) < 4:
        return False
    return pdf_bytes.startswith(PDF_SIGNATURE)


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


def _parse_multipart_form_data(body, content_type):
    """
    Parse multipart/form-data from Lambda event body.

    Returns dict with 'pdfs' and 'jsons' arrays containing file data.
    Each file is a dict with 'filename', 'content' (bytes), and 'content_type'.

    Note: This is a simplified parser. In production, consider using a library
    like python-multipart for more robust parsing.
    """
    import re

    # Extract boundary from content-type header (e.g., "boundary=----WebKitFormBoundary...")
    boundary_match = re.search(r'boundary=([^;]+)', content_type)
    if not boundary_match:
        raise ValueError("No boundary found in content-type header")

    boundary = boundary_match.group(1).strip('"')
    boundary_bytes = f'--{boundary}'.encode('utf-8')

    # Decode body if it's base64 encoded (API Gateway v2 automatically encodes binary data as base64)
    if isinstance(body, str):
        try:
            body_bytes = base64.b64decode(body)
        except Exception:
            # If base64 decode fails, assume it's already plain text
            body_bytes = body.encode('utf-8')
    else:
        body_bytes = body

    # Split multipart body into individual parts using the boundary marker
    parts = body_bytes.split(boundary_bytes)

    files = {'pdfs': [], 'jsons': []}

    for part in parts:
        # Skip empty parts and terminating boundary markers
        if not part or part == b'--\r\n' or part == b'--':
            continue

        # Each part has headers followed by content, separated by \r\n\r\n
        if b'\r\n\r\n' in part:
            headers_section, content = part.split(b'\r\n\r\n', 1)
        else:
            continue

        # Remove trailing CRLF and boundary markers from content
        content = content.rstrip(b'\r\n')

        # Parse Content-Disposition header to extract field name and filename
        # Example: Content-Disposition: form-data; name="pdfs"; filename="invoice-001.pdf"
        headers_str = headers_section.decode('utf-8', errors='ignore')

        filename_match = re.search(r'filename="([^"]+)"', headers_str)
        field_name_match = re.search(r'name="([^"]+)"', headers_str)

        if not filename_match or not field_name_match:
            continue

        filename = filename_match.group(1)
        field_name = field_name_match.group(1)

        # Extract optional Content-Type header (e.g., "Content-Type: application/pdf")
        content_type_match = re.search(r'Content-Type:\s*([^\r\n]+)', headers_str)
        file_content_type = content_type_match.group(1) if content_type_match else 'application/octet-stream'

        file_data = {
            'filename': filename,
            'content': content,
            'content_type': file_content_type
        }

        # Categorize files by form field name (pdfs vs jsons)
        if field_name == 'pdfs':
            files['pdfs'].append(file_data)
        elif field_name == 'jsons':
            files['jsons'].append(file_data)

    return files


def _validate_invoice_json(json_data):
    """
    Validate sidecar JSON schema.

    Required fields:
    - invoiceNumber: string
    - date: string (YYYY-MM-DD format)
    - amount: number

    Optional but recommended:
    - weekStart, weekEnd, clientName, hours, rate, dailyHours

    Returns (is_valid, error_message)
    """
    required_fields = ['invoiceNumber', 'date', 'amount']

    for field in required_fields:
        if field not in json_data:
            return False, f"Missing required field: {field}"

    # Validate invoiceNumber is a non-empty string
    invoice_num = json_data.get('invoiceNumber')
    if not isinstance(invoice_num, str) or not invoice_num.strip():
        return False, "invoiceNumber must be a non-empty string"

    # Validate date format and reasonable range
    try:
        date_obj = datetime.strptime(json_data['date'], '%Y-%m-%d')
        # Ensure date is within reasonable range (1990 to 10 years in future)
        # This prevents data pollution from malformed dates
        min_year = 1990
        max_year = datetime.now(timezone.utc).year + 10
        if date_obj.year < min_year or date_obj.year > max_year:
            return False, f"Invoice date must be between {min_year} and {max_year}"
    except ValueError:
        return False, "Invalid date format (expected YYYY-MM-DD)"

    # Validate amount is a number
    try:
        float(json_data['amount'])
    except (ValueError, TypeError):
        return False, "Invalid amount (must be a number)"

    return True, None


def _create_invoice_record(user_id, json_data, pdf_s3_key):
    """
    Create invoice record from sidecar JSON data and PDF location.

    Maps sidecar JSON schema to DynamoDB Invoices table schema.
    """
    # Generate unique invoiceId from date + invoice number
    # Format: INV-YYYYMMDD-{invoiceNumber} to ensure uniqueness when multiple invoices exist per day
    # This serves as the sort key for DynamoDB queries by date range
    date_obj = datetime.strptime(json_data['date'], '%Y-%m-%d')
    # Sanitize invoice number for use in ID (remove spaces, special chars)
    sanitized_invoice_num = json_data.get('invoiceNumber', '').replace(' ', '-').replace('/', '-')
    invoice_id = f"INV-{date_obj.strftime('%Y%m%d')}-{sanitized_invoice_num}"

    # Build invoice record matching DynamoDB Invoices table schema (see docs/ADR-webapp-migration.md)
    invoice = {
        'userId': user_id,  # Partition key - ensures multi-tenant isolation
        'invoiceId': invoice_id,  # Sort key - enables efficient date range queries
        'invoiceNumber': json_data.get('invoiceNumber', ''),  # User-visible invoice number (e.g., "INV-047")
        'type': 'weekly',  # Default to weekly for historical imports
        'status': 'sent',  # Historical invoices are assumed to have been sent already
        'weekStart': json_data.get('weekStart', json_data['date']),
        'weekEnd': json_data.get('weekEnd', json_data['date']),
        'dueDate': json_data.get('dueDate', json_data['date']),
        'dailyHours': json_data.get('dailyHours', {}),  # e.g., {"Mon": 8, "Tue": 8, ...}
        'totalHours': json_data.get('hours', 0),
        'rate': json_data.get('rate', 0),
        'subtotal': json_data.get('amount', 0),
        'taxRate': 0,  # Historical imports assumed to not have tax
        'taxAmount': 0,
        'totalPay': json_data.get('amount', 0),
        'pdfKey': pdf_s3_key,  # S3 location of PDF file
        'sentAt': json_data.get('sentAt', datetime.now(timezone.utc).isoformat()),
        'sentTo': [json_data.get('clientEmail', '')] if json_data.get('clientEmail') else [],
        'createdAt': datetime.now(timezone.utc).isoformat(),
        'importedAt': datetime.now(timezone.utc).isoformat(),  # Mark as imported (not generated in app)
    }

    # Add client info if available
    if 'clientName' in json_data:
        # For historical imports, we don't have clientId since client records may not exist yet
        # Store client name directly - user can later associate with proper client records via UI
        invoice['clientName'] = json_data['clientName']

    return invoice


def handler(event, context):
    """
    Lambda handler for POST /api/import — import historical invoices with sidecar JSON.

    Expects multipart/form-data with:
    - pdfs: PDF files
    - jsons: Corresponding JSON metadata files

    Each PDF should have a matching JSON file with the same basename.

    Returns:
    - imported: count of successfully imported invoices
    - failed: count of failed imports
    - errors: array of error messages

    Note: CORS is handled by API Gateway (configured in sst.config.ts).
    Lambda functions should not set CORS headers.
    """
    # Response headers
    headers = {
        'Content-Type': 'application/json',
    }

    try:
        # Extract HTTP method
        http_method = event.get('requestContext', {}).get('http', {}).get('method') or event.get('httpMethod', 'POST')

        # Extract and validate authorization
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

        # Verify user exists
        user = get_user(user_id)
        if not user:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'User not found'})
            }

        # Parse multipart form data
        content_type = event.get('headers', {}).get('content-type') or event.get('headers', {}).get('Content-Type', '')

        if 'multipart/form-data' not in content_type:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Content-Type must be multipart/form-data'})
            }

        body = event.get('body', '')
        files = _parse_multipart_form_data(body, content_type)

        # Create lookup maps for efficient file matching by filename
        pdf_map = {f['filename']: f for f in files.get('pdfs', [])}
        json_map = {f['filename']: f for f in files.get('jsons', [])}

        imported = 0
        failed = 0
        errors = []

        # Process each JSON file and find its matching PDF
        # The sidecar pattern requires: invoice-001.json + invoice-001.pdf
        for json_filename, json_file in json_map.items():
            # Extract basename without extension (e.g., "invoice-001.json" → "invoice-001")
            basename = json_filename.rsplit('.', 1)[0]
            pdf_filename = f"{basename}.pdf"

            try:
                # Check for matching PDF with same basename
                if pdf_filename not in pdf_map:
                    errors.append(f"No matching PDF found for {json_filename}")
                    failed += 1
                    continue

                pdf_file = pdf_map[pdf_filename]

                # Validate PDF magic bytes
                if not _validate_pdf_magic_bytes(pdf_file['content']):
                    errors.append(f"{pdf_filename} is not a valid PDF file")
                    failed += 1
                    continue

                # Validate PDF size
                if len(pdf_file['content']) > MAX_FILE_SIZE:
                    errors.append(f"{pdf_filename} exceeds maximum file size (10MB)")
                    failed += 1
                    continue

                # Parse and validate JSON
                try:
                    json_data = json.loads(json_file['content'].decode('utf-8'))
                except json.JSONDecodeError as e:
                    errors.append(f"Malformed JSON in {json_filename}: {str(e)}")
                    failed += 1
                    continue

                is_valid, validation_error = _validate_invoice_json(json_data)
                if not is_valid:
                    errors.append(f"Invalid JSON in {json_filename}: {validation_error}")
                    failed += 1
                    continue

                # Generate S3 key for PDF using multi-tenant isolation pattern
                # Format: users/{userId}/weekly/{invoiceId}.pdf
                # This ensures users can only access their own files via signed URLs
                # Use same unique ID generation as _create_invoice_record to ensure consistency
                date_obj = datetime.strptime(json_data['date'], '%Y-%m-%d')
                sanitized_invoice_num = json_data.get('invoiceNumber', '').replace(' ', '-').replace('/', '-')
                invoice_id = f"INV-{date_obj.strftime('%Y%m%d')}-{sanitized_invoice_num}"
                s3_key = f"users/{user_id}/weekly/{invoice_id}.pdf"

                # Upload PDF to S3 with metadata for tracking
                s3_client.put_object(
                    Bucket=BUCKET_NAME,
                    Key=s3_key,
                    Body=pdf_file['content'],
                    ContentType='application/pdf',
                    Metadata={
                        'uploaded-by': user_id,
                        'import-timestamp': datetime.now(timezone.utc).isoformat(),
                        'original-filename': pdf_filename
                    }
                )

                # Create invoice record in DynamoDB with reference to S3 PDF location
                invoice = _create_invoice_record(user_id, json_data, s3_key)
                put_invoice(invoice)  # This will overwrite if invoiceId already exists

                imported += 1

            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                errors.append(f"AWS error processing {json_filename}: {error_code}")
                failed += 1
                logger.error(f"AWS error: {error_code} - {str(e)}")
            except Exception as e:
                errors.append(f"Error processing {json_filename}: {str(e)}")
                failed += 1
                logger.error(f"Unexpected error: {str(e)}")

        # Return results
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'imported': imported,
                'failed': failed,
                'errors': errors,
                'message': f"Import complete: {imported} successful, {failed} failed"
            })
        }

    except Exception as e:
        logger.error(f"Unhandled error in import handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error during import'})
        }
