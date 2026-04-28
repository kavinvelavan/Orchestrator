import json
import os
import logging

from services import S3StorageService, LambdaService, WebhookProcessor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class LoggingWebhookHandler:
    def __init__(self):
        self.lambda_service = LambdaService()
        self.webhook_processor = WebhookProcessor()
        
        # Environment variables
        self.dependent_services_lambda = os.getenv('DEPENDENT_SERVICES_LAMBDA', 'get-dependent-services')
        self.error_logs_lambda = os.getenv('ERROR_LOGS_LAMBDA', 'get-error-logs')
        self.s3_bucket_name = os.getenv('S3_BUCKET_NAME', 'error-monitoring-bucket')
        
        # Initialize S3 storage service
        self.storage_service = S3StorageService(self.s3_bucket_name)
        
    def lambda_handler(self, event, context):
        """
        Main Lambda handler for logging platform webhook
        """
        try:
            logger.info(f"Received webhook event: {json.dumps(event)}")
            
            # Parse webhook payload
            app_name, timestamp = self.webhook_processor.parse_webhook_payload(event)
            
            # Get dependent services
            dependent_services = self.lambda_service.invoke_dependent_services_lambda(
                self.dependent_services_lambda, app_name
            )
            
            # Get error logs for all dependent services
            error_logs = self.lambda_service.invoke_error_logs_lambda(
                self.error_logs_lambda, dependent_services, timestamp
            )
            
            # Create standardized error response
            error_response = self.webhook_processor.create_error_response(
                app_name, timestamp, dependent_services, error_logs
            )
            
            # Store error data to S3
            storage_success = self.storage_service.store_error_data(error_response)
            if not storage_success:
                logger.warning("Failed to store error data to S3, but continuing with response")
            
            logger.info(f"Successfully processed webhook for application: {app_name}")
            return {
                'statusCode': 200,
                'body': json.dumps(error_response, default=str),
                'headers': {
                    'Content-Type': 'application/json'
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Internal server error',
                    'message': str(e)
                }),
                'headers': {
                    'Content-Type': 'application/json'
                }
            }
    

# Lambda handler function
def lambda_handler(event, context):
    """
    AWS Lambda entry point
    """
    handler = LoggingWebhookHandler()
    return handler.lambda_handler(event, context)

# For local testing with mock services
if __name__ == "__main__":
    from unittest.mock import Mock, patch
    
    # Mock environment variables
    os.environ['DEPENDENT_SERVICES_LAMBDA'] = 'get-dependent-services'
    os.environ['ERROR_LOGS_LAMBDA'] = 'get-error-logs'
    os.environ['S3_BUCKET_NAME'] = 'test-bucket'
    
    # Mock AWS services for local testing
    with patch('boto3.client') as mock_boto3_client:
        # Create mock clients
        mock_lambda_client = Mock()
        mock_s3_client = Mock()
        
        def client_side_effect(service_name, **kwargs):
            if service_name == 'lambda':
                return mock_lambda_client
            elif service_name == 's3':
                return mock_s3_client
            return Mock()
        
        mock_boto3_client.side_effect = client_side_effect
        
        # Create mock payload objects
        mock_payload1 = Mock()
        mock_payload2 = Mock()
        
        # Setup mock response data
        def mock_payload_read1():
            return json.dumps({
                'dependent_services': ['auth-service', 'database-service', 'notification-service']
            }).encode('utf-8')
        
        def mock_payload_read2():
            return json.dumps({
                'error_logs': {
                    'auth-service': [{'level': 'INFO', 'message': 'Authentication successful'}],
                    'database-service': [
                        {'level': 'ERROR', 'message': 'Connection timeout', 'error_code': 'DB_TIMEOUT', 'timestamp': '2024-04-28T10:29:45Z'},
                        {'level': 'ERROR', 'message': 'Query failed', 'error_code': 'QUERY_ERROR', 'timestamp': '2024-04-28T10:29:50Z'}
                    ],
                    'notification-service': [{'level': 'INFO', 'message': 'Notifications sent'}]
                }
            }).encode('utf-8')
        
        mock_payload1.read = mock_payload_read1
        mock_payload2.read = mock_payload_read2
        
        # Mock Lambda responses
        mock_lambda_client.invoke.side_effect = [
            # First call (dependent services)
            {'Payload': mock_payload1},
            # Second call (error logs)
            {'Payload': mock_payload2}
        ]
        
        # Mock S3 response
        mock_s3_client.put_object.return_value = {}
        
        # Test event
        test_event = {
            "body": json.dumps({
                "application_name": "payment-service",
                "timestamp": "2024-04-28T10:30:00Z"
            })
        }
        
        # Mock context
        class MockContext:
            def __init__(self):
                self.function_name = "test-function"
                self.function_version = "$LATEST"
                self.invoked_function_arn = f"arn:aws:lambda:us-east-1:681583877784:function:test-function"
                self.memory_limit_in_mb = 128
                self.aws_request_id = "test-request-id"
                self.log_group_name = "/aws/lambda/test-function"
                self.log_stream_name = "2024/04/28/[$LATEST]test-stream"
        
        print("=== Testing Logging Webhook Handler ===")
        print("\nTest Event:")
        print(json.dumps(test_event, indent=2))
        
        # Test the handler
        try:
            result = lambda_handler(test_event, MockContext())
            print("\n=== SUCCESS ===")
            print("\nResponse:")
            print(json.dumps(result, indent=2))
            
            # Parse and display the response body
            if result['statusCode'] == 200:
                response_body = json.loads(result['body'])
                print("\n=== Processed Error Data ===")
                print(f"Application: {response_body['application_name']}")
                print(f"Alert Timestamp: {response_body['alert_timestamp']}")
                print(f"Dependent Services: {response_body['dependent_services']}")
                print(f"Failed Services: {len(response_body['failed_services'])}")
                
                for failed_service in response_body['failed_services']:
                    print(f"  - {failed_service['service_name']}: {failed_service['error_code']} - {failed_service['error_message']}")
                
                print(f"\nService Hierarchy:")
                for service in response_body['service_hierarchy']:
                    print(f"  - {service['service_name']}: {service['status']} ({service['error_count']} errors)")
                
                print("\n=== S3 Storage ===")
                print("Error data stored to S3 successfully")
                
                # Verify S3 was called
                if mock_s3_client.put_object.called:
                    call_args = mock_s3_client.put_object.call_args
                    print(f"S3 Bucket: {call_args[1]['Bucket']}")
                    print(f"S3 Key: {call_args[1]['Key']}")
            
        except Exception as e:
            print(f"\n=== ERROR ===")
            print(f"Test failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print("\n=== Test Complete ===")
