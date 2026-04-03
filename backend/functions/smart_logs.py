import json


def handler(event, context):
    """
    Lambda handler for POST /api/logs/* — voice transcription, note reformatting, OCR (Pro).
    TODO: Implement in Phase 7.
    """
    return {
        'statusCode': 501,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'error': 'Not yet implemented'})
    }
