"""
Centralized logging configuration for Lambda functions.

This module provides a single source of truth for logging setup across all
Lambda functions, eliminating duplicate basicConfig() calls and enabling
consistent logging behavior.
"""

import logging
import os


def setup_logging():
    """
    Configure root logger for Lambda function execution.

    This function should be called once at module level in each Lambda handler file.
    It configures the root logger with:
    - Log level from LOG_LEVEL environment variable (default: INFO)
    - Consistent format across all functions
    - CloudWatch-friendly output

    Note: basicConfig() is idempotent - if the root logger is already configured,
    this will have no effect. This is safe to call from multiple Lambda functions
    when they share a container.
    """
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()

    # Validate log level
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        # Fall back to INFO if invalid level specified
        numeric_level = logging.INFO

    logging.basicConfig(
        level=numeric_level,
        format='%(levelname)s: %(message)s'
    )
