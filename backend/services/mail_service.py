"""
Email Service

Sends invoice PDFs via AWS SES.
Email body template functions carried over from desktop app.

Functions:
    send_email(to_addresses, subject, body_text, attachments, from_email) -> dict
    create_weekly_email_body(name, week_start, week_end, total_hours, total_pay) -> str
    create_weekly_with_logs_email_body(name, week_start, week_end, total_hours, total_pay) -> str
    create_monthly_email_body(name, month_label, total_hours, total_pay) -> str
"""

import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from botocore.exceptions import ClientError


def send_email(to_addresses, subject, body_text, attachments=None, from_email="noreply@goinvoi.com"):
    """
    Send email via AWS SES with optional PDF attachments.

    Args:
        to_addresses: list of str, recipient email addresses
        subject: str, email subject line
        body_text: str, plain text email body
        attachments: list of dict, optional. Each dict has:
            - 'filename': str, name of attachment (e.g., "invoice.pdf")
            - 'data': bytes, file content
        from_email: str, sender address (default: noreply@goinvoi.com)

    Returns:
        dict: SES response with MessageId on success

    Raises:
        ClientError: if SES send fails
        ValueError: if to_addresses is empty or invalid
    """
    if not to_addresses:
        raise ValueError("to_addresses cannot be empty")

    # Ensure to_addresses is a list
    if isinstance(to_addresses, str):
        to_addresses = [to_addresses]

    # Create MIME multipart message
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = ', '.join(to_addresses)

    # Attach body text
    msg.attach(MIMEText(body_text, 'plain'))

    # Attach PDF files if provided
    if attachments:
        for attachment in attachments:
            part = MIMEApplication(attachment['data'])
            part.add_header(
                'Content-Disposition',
                'attachment',
                filename=attachment['filename']
            )
            msg.attach(part)

    # Send via SES
    ses_client = boto3.client('ses')

    try:
        response = ses_client.send_raw_email(
            Source=from_email,
            Destinations=to_addresses,
            RawMessage={'Data': msg.as_string()}
        )
        return response
    except ClientError as e:
        # Log error and re-raise
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"SES send failed: {error_code} - {error_message}")
        raise


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
