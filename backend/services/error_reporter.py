"""
Per-request error reporting via SNS.

Publishes a message to the configured alarm SNS topic when a Lambda handler
encounters an unexpected exception. This supplements the aggregate CloudWatch
error-rate alarms: those are threshold-based and can miss single-user bugs on
low-volume endpoints, while this fires on the very first failure.

The publish is best-effort. Any failure inside the reporter is logged and
swallowed so it can never turn a 500 into a crash loop.
"""

import json
import logging
import os
import traceback
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

_ALARM_TOPIC_ARN_ENV = "ALARM_TOPIC_ARN"
_sns_client = None


def _get_client():
    global _sns_client
    if _sns_client is None:
        _sns_client = boto3.client("sns")
    return _sns_client


def report_exception(handler_name, exc, event=None, user_id=None, extra=None):
    """
    Publish a single-exception report to the alarm SNS topic.

    Args:
        handler_name: str — short identifier for the handler (e.g. "submit_weekly").
        exc: the exception instance being reported.
        event: optional Lambda event dict — HTTP method/path will be extracted.
        user_id: optional user identifier associated with the request.
        extra: optional dict of additional context to include in the report.

    Returns:
        True if the SNS publish succeeded, False otherwise. Never raises.
    """
    topic_arn = os.environ.get(_ALARM_TOPIC_ARN_ENV)
    if not topic_arn:
        # No topic configured (local tests, dev stage without alarms wired up).
        return False

    try:
        http_ctx = {}
        if event:
            req_ctx = event.get("requestContext", {}) or {}
            http_ctx = req_ctx.get("http", {}) or {}

        payload = {
            "handler": handler_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": os.environ.get("SST_STAGE") or os.environ.get("STAGE", "unknown"),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": traceback.format_exc(),
            "user_id": user_id,
            "method": http_ctx.get("method"),
            "path": http_ctx.get("path"),
            "request_id": (event or {}).get("requestContext", {}).get("requestId"),
        }
        if extra:
            payload["extra"] = extra

        subject = f"[invoi] {handler_name} 500: {type(exc).__name__}"[:100]

        _get_client().publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=json.dumps(payload, default=str, indent=2),
        )
        return True
    except (BotoCoreError, ClientError) as sns_err:
        logger.error(
            "error_reporter: failed to publish exception report: %s", sns_err
        )
        return False
    except Exception as unexpected:
        logger.error(
            "error_reporter: unexpected failure while reporting exception: %s",
            unexpected,
        )
        return False
