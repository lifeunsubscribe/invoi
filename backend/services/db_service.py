import boto3
from os import environ
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')


def get_users_table():
    return dynamodb.Table(environ['USERS_TABLE'])


def get_invoices_table():
    return dynamodb.Table(environ['INVOICES_TABLE'])


def get_user(user_id):
    """
    Retrieve a user record from the Users table.

    Args:
        user_id (str): The userId (Cognito sub) to retrieve

    Returns:
        dict: User record if found, None if not found

    Raises:
        ClientError: If DynamoDB operation fails
    """
    try:
        table = get_users_table()
        response = table.get_item(Key={'userId': user_id})
        return response.get('Item')
    except ClientError as e:
        # Re-raise for caller to handle
        raise


def put_user(user_data):
    """
    Create or update a user record in the Users table.

    Args:
        user_data (dict): User record containing at minimum 'userId'

    Returns:
        dict: The user data that was written

    Raises:
        ValueError: If userId is missing from user_data
        ClientError: If DynamoDB operation fails
    """
    if 'userId' not in user_data:
        raise ValueError("user_data must contain 'userId' field")

    try:
        table = get_users_table()
        table.put_item(Item=user_data)
        return user_data
    except ClientError as e:
        raise


def get_invoice(user_id, invoice_id):
    """
    Retrieve a single invoice from the Invoices table.

    Args:
        user_id (str): The userId (partition key)
        invoice_id (str): The invoiceId (sort key), e.g., 'INV-20260324'

    Returns:
        dict: Invoice record if found, None if not found

    Raises:
        ClientError: If DynamoDB operation fails
    """
    try:
        table = get_invoices_table()
        response = table.get_item(
            Key={
                'userId': user_id,
                'invoiceId': invoice_id
            }
        )
        return response.get('Item')
    except ClientError as e:
        raise


def put_invoice(invoice_data):
    """
    Create or update an invoice record in the Invoices table.

    Args:
        invoice_data (dict): Invoice record containing at minimum 'userId' and 'invoiceId'

    Returns:
        dict: The invoice data that was written

    Raises:
        ValueError: If userId or invoiceId is missing from invoice_data
        ClientError: If DynamoDB operation fails
    """
    if 'userId' not in invoice_data or 'invoiceId' not in invoice_data:
        raise ValueError("invoice_data must contain 'userId' and 'invoiceId' fields")

    try:
        table = get_invoices_table()
        table.put_item(Item=invoice_data)
        return invoice_data
    except ClientError as e:
        raise


def query_invoices(user_id, filters=None):
    """
    Query invoices for a user with optional filtering.

    Args:
        user_id (str): The userId to query invoices for
        filters (dict, optional): Filter criteria with the following supported keys:
            - 'status' (str): Filter by status (draft/sent/paid/overdue)
            - 'clientId' (str): Filter by client ID
            - 'type' (str): Filter by invoice type (weekly/monthly)
            - 'invoiceId_start' (str): Filter invoices >= this invoiceId (for date ranges)
            - 'invoiceId_end' (str): Filter invoices <= this invoiceId (for date ranges)

    Returns:
        list: List of invoice records matching the query

    Raises:
        ClientError: If DynamoDB operation fails

    Examples:
        # Get all invoices for a user
        query_invoices('user123')

        # Get paid invoices
        query_invoices('user123', {'status': 'paid'})

        # Get invoices for March 2026
        query_invoices('user123', {
            'invoiceId_start': 'INV-20260301',
            'invoiceId_end': 'INV-20260331'
        })
    """
    try:
        table = get_invoices_table()

        # Build the key condition for the partition key
        key_condition = Key('userId').eq(user_id)

        # Add sort key condition if date range filtering is requested
        if filters and ('invoiceId_start' in filters or 'invoiceId_end' in filters):
            start = filters.get('invoiceId_start')
            end = filters.get('invoiceId_end')

            if start and end:
                key_condition = key_condition & Key('invoiceId').between(start, end)
            elif start:
                key_condition = key_condition & Key('invoiceId').gte(start)
            elif end:
                key_condition = key_condition & Key('invoiceId').lte(end)

        # Build filter expressions for non-key attributes
        filter_expression = None
        if filters:
            filter_parts = []

            if 'status' in filters:
                filter_parts.append(Attr('status').eq(filters['status']))

            if 'clientId' in filters:
                filter_parts.append(Attr('clientId').eq(filters['clientId']))

            if 'type' in filters:
                filter_parts.append(Attr('type').eq(filters['type']))

            # Combine filter parts with AND
            if filter_parts:
                filter_expression = filter_parts[0]
                for part in filter_parts[1:]:
                    filter_expression = filter_expression & part

        # Execute query
        query_params = {'KeyConditionExpression': key_condition}
        if filter_expression:
            query_params['FilterExpression'] = filter_expression

        response = table.query(**query_params)
        items = response.get('Items', [])

        # Handle pagination if there are more results
        while 'LastEvaluatedKey' in response:
            query_params['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = table.query(**query_params)
            items.extend(response.get('Items', []))

        return items

    except ClientError as e:
        raise
