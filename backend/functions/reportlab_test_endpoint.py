"""
Test Lambda function to verify ReportLab layer import.

This is a temporary test function for Phase 2.
It verifies that the ReportLab Lambda layer is correctly installed
and can be imported by Lambda functions.

Returns a JSON response with ReportLab version info.
"""

import json


def handler(event, context):
    """
    Test handler that attempts to import ReportLab.

    Returns:
        dict: Response with statusCode 200 if ReportLab imports successfully,
              or 500 if import fails.
    """
    try:
        # Test ReportLab import
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.units import inch
        from reportlab import Version

        # Test Pillow import (ReportLab dependency)
        from PIL import Image
        import PIL

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps({
                'success': True,
                'message': 'ReportLab layer working correctly',
                'reportlab_version': Version,
                'pillow_version': PIL.__version__,
                'test_imports': {
                    'letter_size': letter,
                    'a4_size': A4,
                    'inch_unit': inch,
                }
            })
        }
    except ImportError as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps({
                'success': False,
                'error': f'ImportError: {str(e)}',
                'message': 'ReportLab layer not available or misconfigured'
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
            },
            'body': json.dumps({
                'success': False,
                'error': str(e),
                'message': 'Unexpected error during ReportLab test'
            })
        }
