"""Pytest configuration and fixtures for backend tests"""
import sys
import os
from unittest.mock import MagicMock, patch

# Set required environment variables before any imports
os.environ['INVOICES_TABLE'] = 'invoices-table'
os.environ['USERS_TABLE'] = 'users-table'
os.environ['SST_Resource_InvoiStorage_name'] = 'test-bucket'

# Mock xhtml2pdf before any imports
sys.modules['xhtml2pdf'] = MagicMock()
sys.modules['xhtml2pdf.pisa'] = MagicMock()

# Mock AWS credentials for boto3 clients created at module level
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
