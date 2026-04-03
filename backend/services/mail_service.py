"""
Email Service

Sends invoice PDFs via AWS SES.
Email body template functions carried over from desktop app.

Functions:
    send_email(to_addresses, subject, body_text, attachments) -> dict
    create_weekly_email_body(name, week_start, week_end, total_hours, total_pay) -> str
    create_weekly_with_logs_email_body(name, week_start, week_end, total_hours, total_pay) -> str
    create_monthly_email_body(name, month_label, total_hours, total_pay) -> str
"""

import boto3


def send_email(to_addresses, subject, body_text, attachments=None):
    """
    Send email via AWS SES.
    TODO: Implement in Phase 3 (Email).
    """
    raise NotImplementedError("SES email sending not yet implemented")


def create_weekly_email_body(name, week_start, week_end, total_hours, total_pay):
    """
    Generate plain text email body for weekly invoice.

    Args:
        name: str, provider name (e.g., "Lisa Wadley")
        week_start: str, week start date (e.g., "March 24")
        week_end: str, week end date (e.g., "March 30, 2026")
        total_hours: int or float, total hours worked
        total_pay: float, total amount due

    Returns:
        str: Plain text email body
    """
    return f"""Hi,

Please find attached my invoice for the week of {week_start} \u2013 {week_end}.

Total hours: {total_hours}
Total due: ${total_pay:.2f}

Thank you,
{name}"""


def create_weekly_with_logs_email_body(name, week_start, week_end, total_hours,
                                       total_pay):
    """Generate email body for weekly invoice + service log attachment."""
    return f"""Hi,

Please find attached my invoice and weekly service log for the week of {week_start} \u2013 {week_end}.

Total hours: {total_hours}
Total due: ${total_pay:.2f}

Thank you,
{name}"""


def create_monthly_email_body(name, month_label, total_hours, total_pay):
    """
    Generate plain text email body for monthly report.

    Args:
        name: str, provider name (e.g., "Lisa Wadley")
        month_label: str, month and year (e.g., "March 2026")
        total_hours: int or float, total hours worked in month
        total_pay: float, total invoiced amount for month

    Returns:
        str: Plain text email body
    """
    return f"""Hi,

Attached is my monthly hours summary for {month_label}.

Total hours: {total_hours}
Total invoiced: ${total_pay:.2f}

Please let me know if you need the individual weekly invoices as well.

Thank you,
{name}"""
