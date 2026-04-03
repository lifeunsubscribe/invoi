import boto3
from os import environ

dynamodb = boto3.resource('dynamodb')


def get_users_table():
    return dynamodb.Table(environ['USERS_TABLE'])


def get_invoices_table():
    return dynamodb.Table(environ['INVOICES_TABLE'])

# TODO: Implement CRUD helpers in Phase 1
