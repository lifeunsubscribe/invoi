import json
import sys
import os
from datetime import datetime
import calendar

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.db_service import query_invoices, get_user, put_invoice
from services.pdf_service import generate_monthly_report, save_pdf_to_s3
from botocore.exceptions import ClientError


def handler(event, context):
    """
    Lambda handler for POST /api/submit/monthly — aggregate weekly invoices and generate monthly report PDF.

    Request body (JSON):
        {
            "year": 2026,
            "month": 3
        }

    Returns:
        200: Report metadata including S3 key
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

        year = body.get('year')
        month = body.get('month')

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

        # Generate month label (e.g., "March 2026")
        month_name = calendar.month_name[month_int]
        month_label = f"{month_name} {year_int}"

        # Generate monthly report PDF
        # Uses user's template, rate, and other config from user_config
        pdf_bytes = generate_monthly_report(
            config=user_config,
            week_data=week_data,
            month_label=month_label,
            template_id=user_config.get('template', 'caring-hands'),
            signature_font=user_config.get('signatureFont', ''),
            sign_date=datetime.now().strftime('%Y-%m-%d'),
            invoice_date=datetime.now()
        )

        # Upload PDF to S3 at users/{userId}/reports/RPT-{year}-{month}.pdf
        # SST Ion provides bucket name via SST_Resource_<name>_name when linked
        bucket_name = os.environ['SST_Resource_InvoiStorage_name']
        report_id = f"RPT-{year_int:04d}-{month_int:02d}"
        s3_key = f"users/{user_id}/reports/{report_id}.pdf"

        save_pdf_to_s3(pdf_bytes, bucket_name, s3_key)

        # Calculate totals for metadata
        total_hours = sum(w['hours'] for w in week_data)
        rate = float(user_config.get('rate', 0))
        total_pay = total_hours * rate

        # Save report metadata to Invoices table with type="monthly"
        report_metadata = {
            'userId': user_id,
            'invoiceId': report_id,
            'type': 'monthly',
            'status': 'draft',  # Monthly reports start as draft (not sent yet)
            'year': year_int,
            'month': month_int,
            'monthLabel': month_label,
            'weekCount': len(week_data),
            'totalHours': total_hours,
            'rate': rate,
            'totalPay': total_pay,
            'pdfKey': s3_key,
            'createdAt': datetime.now().isoformat()
        }

        put_invoice(report_metadata)

        # Return report metadata including S3 key
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'reportId': report_id,
                's3Key': s3_key,
                'monthLabel': month_label,
                'totalHours': total_hours,
                'totalPay': total_pay,
                'weekCount': len(week_data),
                'createdAt': report_metadata['createdAt']
            })
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except ClientError as e:
        print(f"AWS error in POST /api/submit/monthly: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to generate monthly report'})
        }
    except Exception as e:
        print(f"Unhandled error in submit_monthly handler: {str(e)}")
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
