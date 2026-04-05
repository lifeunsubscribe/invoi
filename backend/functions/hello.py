import json

# TODO: REMOVE AFTER PHASE 0 - Temporary endpoint for end-to-end verification only

def handler(event, context):
    """
    Lambda handler for GET /hello — end-to-end verification endpoint.
    Returns a simple greeting message to confirm the browser-to-Lambda flow works.

    Note: CORS is handled by API Gateway (configured in sst.config.ts).
    Lambda functions should not set CORS headers.
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
        },
        'body': json.dumps({'message': 'Hello from Invoi'})
    }
