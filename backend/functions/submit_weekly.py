import json


def handler(event, context):
    """
    Lambda handler for POST /api/submit/weekly — generate weekly invoice PDF, store in S3, save metadata.
    TODO: Implement in Phase 2.
    """
    return {
        'statusCode': 501,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': 'Not yet implemented'})
    }
