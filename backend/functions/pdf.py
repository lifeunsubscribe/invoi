import json


def handler(event, context):
    """
    Lambda handler for GET /api/pdf/{invoiceId} — return signed S3 URL for PDF download.
    TODO: Implement in Phase 2.
    """
    return {
        'statusCode': 501,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': 'Not yet implemented'})
    }
