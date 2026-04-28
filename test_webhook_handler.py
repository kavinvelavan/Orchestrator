import unittest
import json
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys
import os

# Add the current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services import S3StorageService, LambdaService, WebhookProcessor
from lambda_webhook_handler import LoggingWebhookHandler, lambda_handler


class TestS3StorageService(unittest.TestCase):
    """Test cases for S3StorageService"""
    
    def setUp(self):
        self.bucket_name = 'test-bucket'
        self.storage_service = S3StorageService(self.bucket_name)
        self.storage_service.s3_client = Mock()
    
    def test_store_error_data_success(self):
        """Test successful storage of error data to S3"""
        error_data = {
            'application_name': 'test-app',
            'alert_timestamp': '2024-04-28T10:30:00Z',
            'dependent_services': ['service1', 'service2'],
            'error_logs': {'service1': []}
        }
        
        # Mock the S3 client response
        self.storage_service.s3_client.put_object.return_value = {}
        
        result = self.storage_service.store_error_data(error_data)
        
        self.assertTrue(result)
        self.storage_service.s3_client.put_object.assert_called_once()
        
        # Verify the S3 key structure
        call_args = self.storage_service.s3_client.put_object.call_args
        self.assertEqual(call_args[1]['Bucket'], self.bucket_name)
        self.assertIn('error-logs/2024/04/28/10/', call_args[1]['Key'])
        self.assertIn('test-app_20240428_103000.json', call_args[1]['Key'])
    
    def test_store_error_data_failure(self):
        """Test failure when storing error data to S3"""
        error_data = {'application_name': 'test-app'}
        
        # Mock S3 client to raise exception
        self.storage_service.s3_client.put_object.side_effect = Exception('S3 error')
        
        result = self.storage_service.store_error_data(error_data)
        
        self.assertFalse(result)
    
    def test_retrieve_error_data_success(self):
        """Test successful retrieval of error data from S3"""
        date = '2024/04/28'
        
        # Mock S3 list_objects_v2 response
        mock_list_response = {
            'Contents': [
                {'Key': 'error-logs/2024/04/28/10/test-app_20240428_103000.json'},
                {'Key': 'error-logs/2024/04/28/11/another-app_20240428_110000.json'}
            ]
        }
        
        # Mock S3 get_object response
        mock_get_response = {
            'Body': Mock()
        }
        mock_get_response['Body'].read.return_value = json.dumps({
            'application_name': 'test-app',
            'alert_timestamp': '2024-04-28T10:30:00Z'
        }).encode('utf-8')
        
        self.storage_service.s3_client.list_objects_v2.return_value = mock_list_response
        self.storage_service.s3_client.get_object.return_value = mock_get_response
        
        result = self.storage_service.retrieve_error_data(date)
        
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.storage_service.s3_client.list_objects_v2.assert_called_once()
    
    def test_retrieve_error_data_with_service_filter(self):
        """Test retrieval of error data with service name filter"""
        date = '2024/04/28'
        service_name = 'test-app'
        
        # Mock empty response
        self.storage_service.s3_client.list_objects_v2.return_value = {}
        
        result = self.storage_service.retrieve_error_data(date, service_name)
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)


class TestLambdaService(unittest.TestCase):
    """Test cases for LambdaService"""
    
    def setUp(self):
        self.lambda_service = LambdaService()
        self.lambda_service.lambda_client = Mock()
    
    def test_invoke_dependent_services_lambda_success(self):
        """Test successful invocation of dependent services Lambda"""
        function_name = 'get-dependent-services'
        app_name = 'test-app'
        
        # Mock Lambda response
        mock_response = {
            'Payload': Mock()
        }
        mock_response['Payload'].read.return_value = json.dumps({
            'dependent_services': ['service1', 'service2', 'service3']
        }).encode('utf-8')
        
        self.lambda_service.lambda_client.invoke.return_value = mock_response
        
        result = self.lambda_service.invoke_dependent_services_lambda(function_name, app_name)
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertIn('service1', result)
        
        # Verify Lambda was called with correct parameters
        call_args = self.lambda_service.lambda_client.invoke.call_args
        self.assertEqual(call_args[1]['FunctionName'], function_name)
        payload = json.loads(call_args[1]['Payload'])
        self.assertEqual(payload['service_name'], app_name)
    
    def test_invoke_dependent_services_lambda_error(self):
        """Test error handling when dependent services Lambda fails"""
        function_name = 'get-dependent-services'
        app_name = 'test-app'
        
        # Mock Lambda error response
        mock_response = {
            'Payload': Mock()
        }
        mock_response['Payload'].read.return_value = json.dumps({
            'errorMessage': 'Lambda function failed'
        }).encode('utf-8')
        
        self.lambda_service.lambda_client.invoke.return_value = mock_response
        
        with self.assertRaises(Exception) as context:
            self.lambda_service.invoke_dependent_services_lambda(function_name, app_name)
        
        self.assertIn('Lambda function error', str(context.exception))
    
    def test_invoke_error_logs_lambda_success(self):
        """Test successful invocation of error logs Lambda"""
        function_name = 'get-error-logs'
        service_names = ['service1', 'service2']
        error_timestamp = '2024-04-28T10:30:00Z'
        
        # Mock Lambda response
        mock_response = {
            'Payload': Mock()
        }
        mock_response['Payload'].read.return_value = json.dumps({
            'error_logs': {
                'service1': [{'level': 'ERROR', 'message': 'Error 1'}],
                'service2': [{'level': 'INFO', 'message': 'Info 1'}]
            }
        }).encode('utf-8')
        
        self.lambda_service.lambda_client.invoke.return_value = mock_response
        
        result = self.lambda_service.invoke_error_logs_lambda(function_name, service_names, error_timestamp)
        
        self.assertIsInstance(result, dict)
        self.assertIn('service1', result)
        self.assertIn('service2', result)
        
        # Verify time calculation (15 minutes before)
        call_args = self.lambda_service.lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        self.assertEqual(payload['service_names'], service_names)
        self.assertEqual(payload['end_time'], error_timestamp)
        
        # Calculate expected start time
        error_time = datetime.fromisoformat(error_timestamp.replace('Z', '+00:00'))
        expected_start_time = (error_time - timedelta(minutes=15)).isoformat()
        self.assertEqual(payload['start_time'], expected_start_time)


class TestWebhookProcessor(unittest.TestCase):
    """Test cases for WebhookProcessor"""
    
    def test_parse_webhook_payload_success(self):
        """Test successful parsing of webhook payload"""
        event = {
            'body': json.dumps({
                'application_name': 'test-app',
                'timestamp': '2024-04-28T10:30:00Z'
            })
        }
        
        app_name, timestamp = WebhookProcessor.parse_webhook_payload(event)
        
        self.assertEqual(app_name, 'test-app')
        self.assertEqual(timestamp, '2024-04-28T10:30:00+00:00')
    
    def test_parse_webhook_payload_missing_fields(self):
        """Test parsing webhook payload with missing required fields"""
        event = {
            'body': json.dumps({
                'application_name': 'test-app'
                # Missing timestamp
            })
        }
        
        with self.assertRaises(ValueError) as context:
            WebhookProcessor.parse_webhook_payload(event)
        
        self.assertIn('Missing required field: timestamp', str(context.exception))
    
    def test_parse_webhook_payload_invalid_timestamp(self):
        """Test parsing webhook payload with invalid timestamp"""
        event = {
            'body': json.dumps({
                'application_name': 'test-app',
                'timestamp': 'invalid-timestamp'
            })
        }
        
        with self.assertRaises(ValueError) as context:
            WebhookProcessor.parse_webhook_payload(event)
        
        self.assertIn('Invalid timestamp format', str(context.exception))
    
    def test_create_error_response(self):
        """Test creation of standardized error response"""
        app_name = 'test-app'
        timestamp = '2024-04-28T10:30:00Z'
        dependent_services = ['service1', 'service2']
        error_logs = {
            'service1': [{'level': 'ERROR', 'message': 'Error 1', 'error_code': 'ERR001', 'timestamp': '2024-04-28T10:29:00Z'}],
            'service2': [{'level': 'INFO', 'message': 'Info 1'}]
        }
        
        response = WebhookProcessor.create_error_response(
            app_name, timestamp, dependent_services, error_logs
        )
        
        self.assertEqual(response['application_name'], app_name)
        self.assertEqual(response['alert_timestamp'], timestamp)
        self.assertEqual(len(response['dependent_services']), 2)
        self.assertIn('failed_services', response)
        self.assertIn('service_hierarchy', response)
        self.assertIn('processed_at', response)
        
        # Check failed services identification
        self.assertEqual(len(response['failed_services']), 1)
        self.assertEqual(response['failed_services'][0]['service_name'], 'service1')
        self.assertEqual(response['failed_services'][0]['error_code'], 'ERR001')
        
        # Check service hierarchy
        self.assertEqual(len(response['service_hierarchy']), 2)
        service1_status = next(s for s in response['service_hierarchy'] if s['service_name'] == 'service1')
        self.assertEqual(service1_status['status'], 'FAILED')
        self.assertEqual(service1_status['error_count'], 1)
    
    def test_identify_failed_services(self):
        """Test identification of failed services from error logs"""
        error_logs = {
            'service1': [
                {'level': 'ERROR', 'message': 'Error 1', 'error_code': 'ERR001'},
                {'level': 'INFO', 'message': 'Info 1'}
            ],
            'service2': [
                {'level': 'INFO', 'message': 'Info 2'}
            ],
            'service3': [
                {'level': 'ERROR', 'message': 'Error 3', 'error_code': 'ERR003'}
            ]
        }
        
        failed_services = WebhookProcessor._identify_failed_services(error_logs)
        
        self.assertEqual(len(failed_services), 2)
        service_names = [fs['service_name'] for fs in failed_services]
        self.assertIn('service1', service_names)
        self.assertIn('service3', service_names)
        self.assertNotIn('service2', service_names)
    
    def test_build_service_hierarchy(self):
        """Test building service hierarchy with error status"""
        dependent_services = ['service1', 'service2', 'service3']
        error_logs = {
            'service1': [{'level': 'ERROR', 'message': 'Error 1'}],
            'service2': [{'level': 'INFO', 'message': 'Info 1'}],
            'service3': [{'level': 'ERROR', 'message': 'Error 2'}, {'level': 'ERROR', 'message': 'Error 3'}]
        }
        
        hierarchy = WebhookProcessor._build_service_hierarchy(dependent_services, error_logs)
        
        self.assertEqual(len(hierarchy), 3)
        
        service1 = next(s for s in hierarchy if s['service_name'] == 'service1')
        self.assertEqual(service1['status'], 'FAILED')
        self.assertEqual(service1['error_count'], 1)
        
        service2 = next(s for s in hierarchy if s['service_name'] == 'service2')
        self.assertEqual(service2['status'], 'HEALTHY')
        self.assertEqual(service2['error_count'], 0)
        
        service3 = next(s for s in hierarchy if s['service_name'] == 'service3')
        self.assertEqual(service3['status'], 'FAILED')
        self.assertEqual(service3['error_count'], 2)


class TestLoggingWebhookHandler(unittest.TestCase):
    """Test cases for LoggingWebhookHandler"""
    
    def setUp(self):
        # Mock environment variables
        with patch.dict(os.environ, {
            'DEPENDENT_SERVICES_LAMBDA': 'get-dependent-services',
            'ERROR_LOGS_LAMBDA': 'get-error-logs',
            'S3_BUCKET_NAME': 'test-bucket'
        }):
            self.handler = LoggingWebhookHandler()
    
    @patch('services.S3StorageService')
    @patch('services.LambdaService')
    def test_lambda_handler_success(self, mock_lambda_service_class, mock_storage_service_class):
        """Test successful Lambda handler execution"""
        # Setup mocks
        mock_lambda_service = Mock()
        mock_lambda_service.invoke_dependent_services_lambda.return_value = ['service1', 'service2']
        mock_lambda_service.invoke_error_logs_lambda.return_value = {
            'service1': [{'level': 'ERROR', 'message': 'Error 1'}],
            'service2': [{'level': 'INFO', 'message': 'Info 1'}]
        }
        mock_lambda_service_class.return_value = mock_lambda_service
        
        mock_storage_service = Mock()
        mock_storage_service.store_error_data.return_value = True
        mock_storage_service_class.return_value = mock_storage_service
        
        # Test event
        event = {
            'body': json.dumps({
                'application_name': 'test-app',
                'timestamp': '2024-04-28T10:30:00Z'
            })
        }
        
        # Mock context
        context = Mock()
        
        result = self.handler.lambda_handler(event, context)
        
        self.assertEqual(result['statusCode'], 200)
        
        # Verify response body
        response_body = json.loads(result['body'])
        self.assertEqual(response_body['application_name'], 'test-app')
        self.assertIn('dependent_services', response_body)
        self.assertIn('error_logs', response_body)
        
        # Verify services were called
        mock_lambda_service.invoke_dependent_services_lambda.assert_called_once()
        mock_lambda_service.invoke_error_logs_lambda.assert_called_once()
        mock_storage_service.store_error_data.assert_called_once()
    
    def test_lambda_handler_invalid_payload(self):
        """Test Lambda handler with invalid payload"""
        event = {
            'body': json.dumps({
                'application_name': 'test-app'
                # Missing timestamp
            })
        }
        
        context = Mock()
        
        result = self.handler.lambda_handler(event, context)
        
        self.assertEqual(result['statusCode'], 500)
        response_body = json.loads(result['body'])
        self.assertIn('error', response_body)


class TestLambdaHandler(unittest.TestCase):
    """Test cases for the main Lambda handler function"""
    
    @patch('lambda_webhook_handler.LoggingWebhookHandler')
    def test_lambda_handler_function(self, mock_handler_class):
        """Test the main Lambda handler function"""
        # Setup mock handler
        mock_handler = Mock()
        mock_handler.lambda_handler.return_value = {
            'statusCode': 200,
            'body': json.dumps({'message': 'success'})
        }
        mock_handler_class.return_value = mock_handler
        
        # Test event and context
        event = {'test': 'event'}
        context = Mock()
        
        result = lambda_handler(event, context)
        
        self.assertEqual(result['statusCode'], 200)
        mock_handler_class.assert_called_once()
        mock_handler.lambda_handler.assert_called_once_with(event, context)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete workflow"""
    
    @patch.dict(os.environ, {
        'DEPENDENT_SERVICES_LAMBDA': 'get-dependent-services',
        'ERROR_LOGS_LAMBDA': 'get-error-logs',
        'S3_BUCKET_NAME': 'test-bucket'
    })
    @patch('boto3.client')
    def test_end_to_end_workflow(self, mock_boto3_client):
        """Test the complete end-to-end workflow"""
        # Mock AWS clients
        mock_lambda_client = Mock()
        mock_s3_client = Mock()
        
        def client_side_effect(service_name, **kwargs):
            if service_name == 'lambda':
                return mock_lambda_client
            elif service_name == 's3':
                return mock_s3_client
            return Mock()
        
        mock_boto3_client.side_effect = client_side_effect
        
        # Mock Lambda responses
        mock_lambda_client.invoke.side_effect = [
            # First call (dependent services)
            {
                'Payload': Mock()
            },
            # Second call (error logs)
            {
                'Payload': Mock()
            }
        ]
        
        mock_lambda_client.invoke.return_value['Payload'].read.return_value = json.dumps({
            'dependent_services': ['service1', 'service2']
        }).encode('utf-8')
        
        # Mock S3 response
        mock_s3_client.put_object.return_value = {}
        
        # Create handler and test
        handler = LoggingWebhookHandler()
        
        event = {
            'body': json.dumps({
                'application_name': 'test-app',
                'timestamp': '2024-04-28T10:30:00Z'
            })
        }
        
        context = Mock()
        
        result = handler.lambda_handler(event, context)
        
        self.assertEqual(result['statusCode'], 200)
        self.assertEqual(mock_lambda_client.invoke.call_count, 2)
        mock_s3_client.put_object.assert_called_once()


if __name__ == '__main__':
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run the tests
    unittest.main(verbosity=2)
