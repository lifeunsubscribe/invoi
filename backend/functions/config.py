import json


def handler(event, context):
    """
    Lambda handler for GET/POST /api/config — user profile management.
    TODO: Implement in Phase 1.
    """
    return {
        'statusCode': 501,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': 'Not yet implemented'})
    }
