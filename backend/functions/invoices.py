import json


def handler(event, context):
    """
    Lambda handler for GET /api/invoices — list, get, and update invoice status.
    TODO: Implement in Phase 3.
    """
    return {
        'statusCode': 501,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': 'Not yet implemented'})
    }
