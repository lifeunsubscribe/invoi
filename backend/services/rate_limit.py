"""
Per-user rate limiting using Lambda warm-instance memory.

Provides a sliding window rate check keyed on user_id. State lives in
module-level memory, so it persists across invocations on the same warm
Lambda instance but resets on cold starts. This is intentional — it catches
rapid-fire abuse from a single user without requiring external storage.

For stage-level (aggregate) rate limiting, see the API Gateway
defaultRouteSettings in sst.config.ts.
"""

import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# {user_id: [timestamp, timestamp, ...]} — persists across warm invocations
_request_log = defaultdict(list)

# Defaults: 10 requests per 60-second window
DEFAULT_MAX_REQUESTS = 10
DEFAULT_WINDOW_SECONDS = 60


def check_rate_limit(user_id, max_requests=DEFAULT_MAX_REQUESTS, window_seconds=DEFAULT_WINDOW_SECONDS):
    """
    Check whether a user has exceeded their per-user rate limit.

    Returns None if within limits, or a 429 response dict if exceeded.
    Caller should return the response dict directly if not None.

    Usage in a handler:
        rate_response = check_rate_limit(user_id)
        if rate_response:
            return rate_response
    """
    now = time.time()
    cutoff = now - window_seconds

    # Prune expired entries
    _request_log[user_id] = [t for t in _request_log[user_id] if t > cutoff]

    if len(_request_log[user_id]) >= max_requests:
        logger.warning(f"Rate limit exceeded for user {user_id}: "
                       f"{len(_request_log[user_id])}/{max_requests} requests in {window_seconds}s window")
        return {
            'statusCode': 429,
            'headers': {'Content-Type': 'application/json'},
            'body': '{"error": "Rate limit exceeded. Please try again later."}'
        }

    _request_log[user_id].append(now)
    return None
