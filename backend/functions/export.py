import json


def handler(event, context):
    """
    Lambda handler for POST /api/export — generate ZIP or CSV of selected invoices.
    TODO: Implement in Phase 4.
    """
    return {
        'statusCode': 501,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': 'Not yet implemented'})
    }
