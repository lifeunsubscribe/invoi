"""
PDF Generation Service

Renders HTML invoice templates to PDF bytes using xhtml2pdf.
Ported from invoice-builder desktop app.

Key changes from desktop version:
- Returns bytes only (no filesystem writes — Lambda handler writes to S3)
- Uses xhtml2pdf instead of WeasyPrint (no GTK dependency in Lambda)
- Template paths relative to backend/templates/
- Supports custom invoice numbers, due dates, tax lines, and logos

Main Functions:
    generate_weekly_invoice(config, hours, week, template_id, ...) -> bytes
    generate_monthly_report(config, week_data, month_label, ...) -> bytes
    render_weekly_log_pdf(config, client, daily_logs, ...) -> bytes

Helpers:
    save_pdf_to_s3(pdf_bytes, bucket_name, key) -> str
    _format_invoice_number(config, invoice_type) -> str
    _calculate_due_date(invoice_date, payment_terms) -> str
"""

import os
import boto3
from io import BytesIO
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader, select_autoescape
from xhtml2pdf import pisa

from backend.themes import (
    WEEKLY_TEMPLATE_FILES,
    MONTHLY_TEMPLATE_FILES,
    LOG_TEMPLATE_FILES,
    THEME_ORDER,
    get_theme,
)

# S3 client for PDF storage (initialized on first use)
_s3_client = None


def _get_s3_client():
    """Lazy-initialize S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3')
    return _s3_client

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_jinja_env():
    """Initialize and return a Jinja2 environment pointing at backend/templates/."""
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(['html', 'xml'])
    )


def _validate_config(config, required_keys):
    """
    Raise ValueError listing any required keys missing from config.

    Args:
        config: dict
        required_keys: list[str]
    Raises:
        ValueError
    """
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")


def _validate_template_id(template_id, template_map):
    """
    Raise ValueError if template_id is not in the given mapping.

    Args:
        template_id: str
        template_map: dict mapping template_id -> filename
    Raises:
        ValueError
    """
    if template_id not in template_map:
        raise ValueError(
            f"Invalid template_id '{template_id}'. "
            f"Must be one of: {', '.join(THEME_ORDER)}"
        )


def _calculate_weekly_totals(hours, rate):
    """
    Return (total_hours: int, total_pay: str) for a weekly hours dict.

    Args:
        hours: dict mapping day name -> hour count
        rate: float
    Returns:
        tuple[int, str]
    """
    total_hours = sum(hours.values())
    return total_hours, f"{total_hours * rate:.2f}"


def _calculate_monthly_totals(week_data, rate):
    """
    Return (total_hours, total_pay, weeks_worked) for a list of week dicts.

    Args:
        week_data: list of dicts with 'hours' key
        rate: float
    Returns:
        tuple[int, str, int]
    """
    total_hours = sum(w.get('hours', 0) for w in week_data)
    weeks_worked = sum(1 for w in week_data if w.get('hours', 0) > 0)
    return total_hours, f"{total_hours * rate:.2f}", weeks_worked


def _calculate_due_date(invoice_date, payment_terms):
    """
    Calculate due date based on invoice date and payment terms.

    Args:
        invoice_date: str or datetime — invoice send/generation date
        payment_terms: str — one of: 'receipt', 'net7', 'net15', 'net30', or 'netN' where N is days

    Returns:
        str — due date in YYYY-MM-DD format

    Examples:
        _calculate_due_date('2026-03-30', 'receipt') → '2026-03-30'
        _calculate_due_date('2026-03-30', 'net7') → '2026-04-06'
        _calculate_due_date('2026-03-30', 'net30') → '2026-04-29'
    """
    # Parse invoice date if it's a string (handle both ISO format and timezone-aware strings)
    if isinstance(invoice_date, str):
        invoice_date = datetime.fromisoformat(invoice_date.replace('Z', '+00:00'))

    # Parse payment terms to extract number of days
    terms_lower = payment_terms.lower().strip()

    if terms_lower == 'receipt':
        # Due immediately upon receipt
        days_to_add = 0
    elif terms_lower.startswith('net'):
        # Extract number from 'net7', 'net15', 'net30', etc.
        # 'net7' → slice [3:] → '7' → int(7) → 7 days
        days_str = terms_lower[3:]
        try:
            days_to_add = int(days_str)
            if days_to_add < 0:
                raise ValueError(
                    f"Invalid payment terms '{payment_terms}'. "
                    "Days must be non-negative (e.g., 'net7', 'net30', not 'net-15')"
                )
        except ValueError as e:
            # Re-raise our custom error message, or provide a generic one
            if "Days must be non-negative" in str(e):
                raise
            raise ValueError(
                f"Invalid payment terms '{payment_terms}'. "
                "Expected 'receipt' or 'netN' where N is a non-negative number (e.g., 'net7', 'net30')"
            )
    else:
        raise ValueError(
            f"Invalid payment terms '{payment_terms}'. "
            "Expected 'receipt' or 'netN' (e.g., 'net7', 'net30')"
        )

    due_date = invoice_date + timedelta(days=days_to_add)
    return due_date.strftime('%Y-%m-%d')


def _format_invoice_number(config, invoice_type='weekly'):
    """
    Generate next invoice number based on user's numbering configuration.

    Args:
        config: dict — user config with 'invoiceNumberConfig' key containing:
            - prefix: str (e.g., 'INV', 'LISA')
            - includeYear: bool
            - separator: str (e.g., '-', '/', '')
            - padding: int (e.g., 3 for '001', 4 for '0001')
            - nextNum: int (current counter value)
        invoice_type: str — 'weekly' or 'monthly' (for potential type-specific prefixes)

    Returns:
        str — formatted invoice number (e.g., 'INV-001', 'LISA-2026-047')

    Note:
        This function does NOT increment the counter — that must be done atomically
        in DynamoDB by the Lambda handler using TransactWriteItems.
    """
    num_config = config.get('invoiceNumberConfig', {})

    # Defaults matching ADR requirements (Phase 2, line 367-379)
    prefix = num_config.get('prefix', 'INV')
    include_year = num_config.get('includeYear', False)
    separator = num_config.get('separator', '-')
    padding = num_config.get('padding', 3)
    next_num = num_config.get('nextNum', 1)

    # Build invoice number by joining parts with separator
    # Examples:
    #   ['INV', '001'] with '-' → 'INV-001'
    #   ['LISA', '2026', '047'] with '-' → 'LISA-2026-047'
    #   ['INV', '0001'] with '' → 'INV0001'
    parts = [prefix]

    if include_year:
        current_year = datetime.now().year
        parts.append(str(current_year))

    # Format number with zero-padding (e.g., 1 → '001' with padding=3)
    num_str = str(next_num).zfill(padding)
    parts.append(num_str)

    return separator.join(parts)


def _render_html_to_pdf(html_content):
    """
    Render HTML string to PDF bytes using xhtml2pdf.

    Args:
        html_content: str — HTML document to convert

    Returns:
        bytes — PDF file contents

    Raises:
        RuntimeError — if PDF generation fails
    """
    output = BytesIO()

    # Convert HTML to PDF using xhtml2pdf (pisa)
    # xhtml2pdf is lighter than WeasyPrint (no GTK dependencies) and works well in Lambda
    pisa_status = pisa.CreatePDF(
        html_content,
        dest=output,
        encoding='utf-8'
    )

    if pisa_status.err:
        raise RuntimeError(
            f"PDF generation failed with {pisa_status.err} errors. "
            "Check HTML template for unsupported CSS or malformed markup."
        )

    pdf_bytes = output.getvalue()
    output.close()

    if not pdf_bytes:
        raise RuntimeError("PDF generation produced empty output")

    return pdf_bytes


def save_pdf_to_s3(pdf_bytes, bucket_name, key):
    """
    Upload PDF bytes to S3.

    Args:
        pdf_bytes: bytes — PDF file contents
        bucket_name: str — S3 bucket name (from environment variable)
        key: str — S3 object key (e.g., 'users/abc123/invoices/2026/INV-001.pdf')

    Returns:
        str — S3 key of uploaded file

    Raises:
        ClientError — if S3 upload fails

    Example:
        pdf_bytes = render_weekly_pdf(...)
        save_pdf_to_s3(
            pdf_bytes,
            os.environ['INVOICES_BUCKET'],
            f'users/{user_id}/invoices/{year}/{invoice_number}.pdf'
        )
    """
    s3 = _get_s3_client()

    s3.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=pdf_bytes,
        ContentType='application/pdf'
    )

    return key


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_weekly_pdf(config, hours, week, template_id,
                      invoice_number=None, invoice_date=None, logo_data=None):
    """
    Render a weekly invoice PDF.

    Args:
        config: dict — must include: name, address, personalEmail, rate,
                clientName, clientEmail, invoiceNote.
                Optional: paymentTerms, taxEnabled, taxRate, taxLabel, invoiceNumberConfig
        hours: dict — day name -> hour count (e.g. {'Monday': 8, ...})
        week: dict — start, end, invNum, dayDates
        template_id: str — must be a key in THEME_ORDER
        invoice_number: str, optional — custom formatted invoice number (e.g., 'INV-001')
                        If None, uses week.invNum or generates from config
        invoice_date: str/datetime, optional — invoice date for due date calculation
                      Defaults to today
        logo_data: str, optional — base64-encoded image data or data URL for logo
                   (e.g., 'data:image/png;base64,iVBORw0KG...')

    Returns:
        bytes — PDF content

    Raises:
        ValueError — bad template_id or missing config keys
        FileNotFoundError — template file missing
        RuntimeError — rendering failure
    """
    _validate_template_id(template_id, WEEKLY_TEMPLATE_FILES)
    _validate_config(config, [
        'name', 'address', 'personalEmail', 'rate',
        'clientName', 'clientEmail', 'invoiceNote',
    ])

    # Validate that rate is a valid number (not just present)
    try:
        rate = float(config['rate'])
        if rate < 0:
            raise ValueError("rate must be a non-negative number")
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid rate value: {e}")

    total_hours, total_pay = _calculate_weekly_totals(hours, rate)

    # Occupation-specific invoice title
    occ_titles = {
        'home-health-aide': 'Home Health Invoice',
        'personal-care': 'Personal Care Invoice',
    }
    invoice_title = occ_titles.get(config.get('occupation', ''), 'Contractor Invoice')

    # Generate invoice number if not provided
    if invoice_number is None:
        # Try week.invNum first (legacy), then generate from config
        invoice_number = week.get('invNum') or _format_invoice_number(config, 'weekly')

    # Calculate due date based on payment terms
    if invoice_date is None:
        invoice_date = datetime.now()
    payment_terms = config.get('paymentTerms', 'receipt')
    due_date = _calculate_due_date(invoice_date, payment_terms)

    # Calculate tax if enabled
    # Tax is applied to the subtotal (hours × rate) and displayed as a separate line item
    # Example: 40 hrs × $28/hr = $1120 subtotal, 8.25% tax = $92.40, total = $1212.40
    tax_enabled = config.get('taxEnabled', False)
    subtotal = total_hours * rate
    tax_amount = 0
    tax_label = config.get('taxLabel', 'Tax')
    tax_rate = config.get('taxRate', 0)  # e.g., 8.25 for 8.25%

    if tax_enabled:
        tax_amount = subtotal * (tax_rate / 100)
        total_with_tax = subtotal + tax_amount
    else:
        total_with_tax = subtotal

    context = {
        'config': config,
        'hours': hours,
        'week': week,
        'total_hours': total_hours,
        'total_pay': total_pay,
        'invoice_title': invoice_title,
        'invoice_number': invoice_number,
        'due_date': due_date,
        'tax_enabled': tax_enabled,
        'subtotal': f"{subtotal:.2f}",
        'tax_rate': tax_rate,
        'tax_amount': f"{tax_amount:.2f}",
        'tax_label': tax_label,
        'total_with_tax': f"{total_with_tax:.2f}",
        'logo_data': logo_data,
    }

    try:
        env = _get_jinja_env()
        tmpl = env.get_template(WEEKLY_TEMPLATE_FILES[template_id])
        html_content = tmpl.render(**context)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Template file not found for '{template_id}': {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to render template '{template_id}': {e}"
        ) from e

    return _render_html_to_pdf(html_content)


def render_monthly_pdf(config, week_data, month_label,
                       template_id='caring-hands',
                       signature_font='', sign_date='',
                       invoice_number=None, invoice_date=None, logo_data=None):
    """
    Render a monthly hours summary PDF.

    Args:
        config: dict — must include: name, address, personalEmail, rate,
                clientName, clientEmail, accountantEmail.
                Optional: paymentTerms, taxEnabled, taxRate, taxLabel, invoiceNumberConfig
        week_data: list of dicts — each with 'label' (str) and 'hours' (int)
        month_label: str — e.g. "March 2026"
        template_id: str — theme to use (default 'caring-hands')
        signature_font: str — Google Font name for cursive signature
        sign_date: str — date string for signature line
        invoice_number: str, optional — custom formatted invoice/report number
        invoice_date: str/datetime, optional — report date for due date calculation
        logo_data: str, optional — base64-encoded image data or data URL for logo

    Returns:
        bytes — PDF content

    Raises:
        ValueError — missing config keys or bad template_id
        FileNotFoundError — template file missing
        RuntimeError — rendering failure
    """
    _validate_template_id(template_id, MONTHLY_TEMPLATE_FILES)
    _validate_config(config, [
        'name', 'address', 'personalEmail', 'rate',
        'clientName', 'clientEmail', 'accountantEmail',
    ])

    # Validate that rate is a valid number (not just present)
    try:
        rate = float(config['rate'])
        if rate < 0:
            raise ValueError("rate must be a non-negative number")
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid rate value: {e}")

    total_hours, total_pay, weeks_worked = _calculate_monthly_totals(
        week_data, rate
    )

    # Generate invoice number if not provided
    if invoice_number is None:
        invoice_number = _format_invoice_number(config, 'monthly')

    # Calculate due date based on payment terms
    if invoice_date is None:
        invoice_date = datetime.now()
    payment_terms = config.get('paymentTerms', 'receipt')
    due_date = _calculate_due_date(invoice_date, payment_terms)

    # Calculate tax if enabled
    # Tax is applied to the subtotal (hours × rate) and displayed as a separate line item
    # Example: 40 hrs × $28/hr = $1120 subtotal, 8.25% tax = $92.40, total = $1212.40
    tax_enabled = config.get('taxEnabled', False)
    subtotal = total_hours * rate
    tax_amount = 0
    tax_label = config.get('taxLabel', 'Tax')
    tax_rate = config.get('taxRate', 0)  # e.g., 8.25 for 8.25%

    if tax_enabled:
        tax_amount = subtotal * (tax_rate / 100)
        total_with_tax = subtotal + tax_amount
    else:
        total_with_tax = subtotal

    context = {
        'config': config,
        'week_data': week_data,
        'month_label': month_label,
        'total_hours': total_hours,
        'total_pay': total_pay,
        'weeks_worked': weeks_worked,
        'signature_font': signature_font,
        'sign_date': sign_date,
        'invoice_number': invoice_number,
        'due_date': due_date,
        'tax_enabled': tax_enabled,
        'subtotal': f"{subtotal:.2f}",
        'tax_rate': tax_rate,
        'tax_amount': f"{tax_amount:.2f}",
        'tax_label': tax_label,
        'total_with_tax': f"{total_with_tax:.2f}",
        'logo_data': logo_data,
    }

    try:
        env = _get_jinja_env()
        tmpl = env.get_template(MONTHLY_TEMPLATE_FILES[template_id])
        html_content = tmpl.render(**context)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Monthly template file not found for '{template_id}': {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to render monthly template '{template_id}': {e}"
        ) from e

    return _render_html_to_pdf(html_content)


def generate_weekly_invoice(config, hours, week, template_id,
                           invoice_number=None, invoice_date=None, logo_data=None):
    """
    Alias for render_weekly_pdf() — provides naming consistency with task description.

    Generate a weekly invoice PDF with custom invoice number, due date, tax line, and logo.

    Args:
        See render_weekly_pdf() for full parameter documentation.

    Returns:
        bytes — PDF content
    """
    return render_weekly_pdf(
        config, hours, week, template_id,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        logo_data=logo_data
    )


def generate_monthly_report(config, week_data, month_label,
                           template_id='caring-hands',
                           signature_font='', sign_date='',
                           invoice_number=None, invoice_date=None, logo_data=None):
    """
    Alias for render_monthly_pdf() — provides naming consistency with task description.

    Generate a monthly hours summary report PDF with custom invoice number, due date, tax, and logo.

    Args:
        See render_monthly_pdf() for full parameter documentation.

    Returns:
        bytes — PDF content

    Note:
        Function signature verified 2026-04-03: All parameters match submit_monthly.py caller.
        Required params (config, week_data, month_label) + optional params
        (template_id, signature_font, sign_date, invoice_date) align with Lambda handler usage.
    """
    return render_monthly_pdf(
        config, week_data, month_label,
        template_id=template_id,
        signature_font=signature_font,
        sign_date=sign_date,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        logo_data=logo_data
    )


def render_weekly_log_pdf(config, client, daily_logs, week_label,
                          template_id='morning-light',
                          signature_font='', sign_date=''):
    """
    Render a consolidated weekly service log PDF (Mon-Fri).

    Args:
        config: dict with provider info (name, address, personalEmail)
        client: dict with patient info (name, address, objective)
        daily_logs: list of 5 dicts (Mon-Fri), each with:
            - date_label: str ("Monday, March 24, 2026")
            - shift: dict with start/end or empty dict
            - vitals: dict or empty dict
            - meds: list of med dicts or empty list
            - sections: list of section dicts or empty list
            - has_data: bool
        week_label: str (e.g., "March 24 – March 28, 2026")
        template_id: str — theme to use (default 'morning-light')
        signature_font: str, Google Font name
        sign_date: str, date for signature line

    Returns:
        bytes: PDF file contents
    """
    _validate_template_id(template_id, LOG_TEMPLATE_FILES)

    # Enrich daily_logs with computed fields
    for day in daily_logs:
        # Compute shift hours
        shift = day.get('shift', {})
        if shift.get('start') and shift.get('end'):
            try:
                sh, sm = map(int, shift['start'].split(':'))
                eh, em = map(int, shift['end'].split(':'))
                diff = (eh * 60 + em) - (sh * 60 + sm)
                day['shift_hours'] = f"{max(0, diff) / 60:.1f}"
            except (ValueError, TypeError):
                day['shift_hours'] = None
        else:
            day['shift_hours'] = None

        # Check if vitals have any non-null values
        vitals = day.get('vitals', {})
        day['has_vitals'] = any(v is not None for v in vitals.values())

    context = {
        'config': config,
        'client': client,
        'daily_logs': daily_logs,
        'week_label': week_label,
        'signature_font': signature_font,
        'sign_date': sign_date,
    }

    try:
        env = _get_jinja_env()
        tmpl = env.get_template(LOG_TEMPLATE_FILES[template_id])
        html_content = tmpl.render(**context)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Log template file not found for '{template_id}': {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to render log template '{template_id}': {e}"
        ) from e

    return _render_html_to_pdf(html_content)
