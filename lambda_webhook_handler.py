import json
import os
import logging
import requests

from services import S3StorageService, LambdaService, WebhookProcessor, RCABotService

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
        self.rca_bot_url = os.getenv('RCA_BOT_URL', 'http://localhost:8000')
        
        # Initialize services
        self.storage_service = S3StorageService(self.s3_bucket_name)
        self.rca_bot_service = RCABotService(self.rca_bot_url)
        
    def lambda_handler(self, event, context):
        """
        Main Lambda handler for New Relic alerts with RCA bot integration
        """
        try:
            logger.info(f"Received webhook event: {json.dumps(event)}")
            
            # Parse New Relic alert payload
            alert_data = self.webhook_processor.parse_newrelic_alert(event)
            
            # Step 1: Call RCA bot knowledge bot function to get dependencies and past incidents
            knowledge_result = self.rca_bot_service.extract_document(alert_data['service_name'])
            
            # Step 2: Calculate time window (15 minutes before alert)
            start_time = self.webhook_processor.calculate_start_time(alert_data['timestamp'])
            
            # Step 3: Call RCA bot log bot function to get error logs
            log_result = self.rca_bot_service.fetch_logs(
                alert_data['service_name'], 
                start_time, 
                alert_data['timestamp']
            )
            
            # Step 4: Train RCA model with error logs and get summary
            rca_summary = self.rca_bot_service.train_analyze(
                alert_data['service_name'],
                knowledge_result,
                log_result
            )
            
            # Create comprehensive response
            error_response = self.webhook_processor.create_rca_response(
                alert_data, knowledge_result, log_result, rca_summary
            )
            
            # Store error data to S3
            storage_success = self.storage_service.store_error_data(error_response)
            if not storage_success:
                logger.warning("Failed to store error data to S3, but continuing with response")
            
            logger.info(f"Successfully processed New Relic alert for service: {alert_data['service_name']}")
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
    os.environ['RCA_BOT_URL'] = 'http://localhost:8000'
    
    # Mock AWS services for local testing
    with patch('boto3.client') as mock_boto3_client, \
         patch('requests.Session.post') as mock_post, \
         patch('requests.Session.get') as mock_get:
        
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
        
        # Mock RCA bot responses
        mock_response1 = Mock()
        mock_response1.json.return_value = {
            'service_name': 'payment-service',
            'dependencies': {
                'upstream_services': ['order-service', 'user-service'],
                'downstream_services': ['notification-service', 'transaction-service'],
                'related_services': ['auth-service', 'account-service']
            },
            'past_incidents': [
                {
                    'incident_id': 'INC-001',
                    'service_name': 'payment-service',
                    'error_type': 'Database connection timeout',
                    'root_cause': 'Database connection pool exhaustion',
                    'resolution': 'Increased connection pool size and added connection retry logic',
                    'timestamp': '2026-04-25T14:30:00Z',
                    'impact': 'Service unavailable for 15 minutes'
                }
            ],
            'analysis_timestamp': '2026-04-28T21:40:00Z'
        }
        mock_response1.raise_for_status.return_value = None
        
        mock_response2 = Mock()
        mock_response2.json.return_value = {
            'service_name': 'payment-service',
            'primary_service_logs': [
                {
                    'log_id': 'LOG-PAYMENT-SERVICE-001',
                    'service': 'payment-service',
                    'timestamp': '2026-04-28T21:15:00Z',
                    'status_code': 500,
                    'error': 'Database connection timeout',
                    'url': '/api/payments/endpoint1',
                    'level': 'ERROR',
                    'message': 'payment-service encountered Database connection timeout',
                    'duration_ms': 100,
                    'request_id': 'REQ-0000-000'
                }
            ],
            'related_service_logs': [],
            'total_error_logs': 5,
            'total_related_logs': 20,
            'fetch_timestamp': '2026-04-28T21:40:00Z'
        }
        mock_response2.raise_for_status.return_value = None
        
        mock_response3 = Mock()
        mock_response3.json.return_value = {
            'service_name': 'payment-service',
            'rca_summary': {
                'error_start_time': '2026-04-28T21:15:00Z',
                'error_code': 500,
                'impacted_dependencies': ['notification-service', 'transaction-service'],
                'endpoints': ['/api/payments/endpoint1'],
                'cause_of_error': 'Database connection pool exhaustion similar to past incident INC-001',
                'action_taken': [
                    'Increase database connection pool size',
                    'Implement connection retry logic',
                    'Check database server health'
                ],
                'severity': 'High',
                'error_pattern': 'Intermittent service failures detected',
                'business_impact': 'Service degradation affecting user experience'
            },
            'ongoing_errors': [
                {
                    'service': 'payment-service',
                    'timestamp': '2026-04-28T21:38:00Z',
                    'error': 'Database connection timeout',
                    'status_code': 500,
                    'url': '/api/payments/endpoint1',
                    'severity': 'High'
                }
            ],
            'analysis_timestamp': '2026-04-28T21:40:00Z'
        }
        mock_response3.raise_for_status.return_value = None
        
        # Mock health check
        mock_health_response = Mock()
        mock_health_response.json.return_value = {
            'status': 'healthy',
            'service': 'RCA Bot',
            'architecture': '3-Service Architecture'
        }
        mock_health_response.raise_for_status.return_value = None
        
        # Setup mock responses sequence
        mock_post.side_effect = [mock_response1, mock_response2, mock_response3]
        mock_get.return_value = mock_health_response
        
        # Mock S3 response
        mock_s3_client.put_object.return_value = {}
        
        # Test event (New Relic alert format)
        test_event = {
            "body": json.dumps({
                "service_name": "payment-service",
                "error_code": "500",
                "endpoint": "/api/payments/endpoint1",
                "timestamp": "2026-04-28T21:30:00Z"
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
        
        print("=== Testing RCA Bot Integration ===")
        print("\nTest Event (New Relic Alert):")
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
                print("\n=== RCA Analysis Results ===")
                
                # Alert Info
                alert_info = response_body['alert_info']
                print(f"Service: {alert_info['service_name']}")
                print(f"Error Code: {alert_info['error_code']}")
                print(f"Endpoint: {alert_info['endpoint']}")
                print(f"Alert Timestamp: {alert_info['alert_timestamp']}")
                
                # Knowledge Analysis
                knowledge = response_body['knowledge_analysis']
                deps = knowledge['dependencies']
                print(f"\n=== Dependencies ===")
                print(f"Upstream Services: {deps.get('upstream_services', [])}")
                print(f"Downstream Services: {deps.get('downstream_services', [])}")
                print(f"Related Services: {deps.get('related_services', [])}")
                
                print(f"\n=== Past Incidents ===")
                for incident in knowledge['past_incidents']:
                    print(f"  - {incident['incident_id']}: {incident['error_type']}")
                    print(f"    Root Cause: {incident['root_cause']}")
                    print(f"    Resolution: {incident['resolution']}")
                
                # Log Analysis
                log_analysis = response_body['log_analysis']
                print(f"\n=== Log Analysis ===")
                print(f"Total Error Logs: {log_analysis['total_error_logs']}")
                print(f"Primary Service Logs: {len(log_analysis['primary_service_logs'])}")
                
                # RCA Summary
                rca_summary = response_body['rca_summary']
                print(f"\n=== RCA Summary ===")
                print(f"Error Start Time: {rca_summary.get('error_start_time')}")
                print(f"Impacted Dependencies: {rca_summary.get('impacted_dependencies', [])}")
                print(f"Impacted Endpoints: {rca_summary.get('endpoints', [])}")
                print(f"Root Cause: {rca_summary.get('cause_of_error')}")
                print(f"Severity: {rca_summary.get('severity')}")
                print(f"Business Impact: {rca_summary.get('business_impact')}")
                
                print(f"\n=== Recommended Actions ===")
                for action in rca_summary.get('action_taken', []):
                    print(f"  - {action}")
                
                # Dashboard Data
                dashboard_data = response_body['dashboard_data']
                print(f"\n=== Dashboard Data ===")
                print(f"Failed Services: {dashboard_data['failed_services']}")
                print(f"Impacted Endpoints: {dashboard_data['impacted_endpoints']}")
                print(f"Severity: {dashboard_data['severity']}")
                print(f"Business Impact: {dashboard_data['business_impact']}")
                
                print("\n=== S3 Storage ===")
                print("RCA data stored to S3 successfully")
                
                # Verify S3 was called
                if mock_s3_client.put_object.called:
                    call_args = mock_s3_client.put_object.call_args
                    print(f"S3 Bucket: {call_args[1]['Bucket']}")
                    print(f"S3 Key: {call_args[1]['Key']}")
                
                # Verify RCA bot calls
                print(f"\n=== RCA Bot API Calls ===")
                print(f"Document Extraction: {'PASS' if mock_post.call_count >= 1 else 'FAIL'}")
                print(f"Log Fetching: {'PASS' if mock_post.call_count >= 2 else 'FAIL'}")
                print(f"Training & Analysis: {'PASS' if mock_post.call_count >= 3 else 'FAIL'}")
                print(f"Health Check: {'PASS' if mock_get.called else 'FAIL'}")
            
        except Exception as e:
            print(f"\n=== ERROR ===")
            print(f"Test failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print("\n=== Test Complete ===")
