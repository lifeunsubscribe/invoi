import json

# TODO: REMOVE AFTER PHASE 0 - Temporary endpoint for end-to-end verification only

def handler(event, context):
    """
    Lambda handler for GET /hello — end-to-end verification endpoint.
    Returns a simple greeting message to confirm the browser-to-Lambda flow works.
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',  # Will be restricted to CloudFront origin in production
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
        'body': json.dumps({'message': 'Hello from Invoi'})
    }
