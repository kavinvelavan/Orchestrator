import json
import boto3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class StorageService(ABC):
    """Abstract base class for storage services"""
    
    @abstractmethod
    def store_error_data(self, error_data: Dict[str, Any]) -> bool:
        """Store error data to storage"""
        pass
    
    @abstractmethod
    def retrieve_error_data(self, date: str, service_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve error data from storage"""
        pass

class S3StorageService(StorageService):
    """S3-based storage service for error data"""
    
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3')
        
    def store_error_data(self, error_data: Dict[str, Any]) -> bool:
        """Store error data to S3 with date/timestamp folder structure"""
        try:
            timestamp = datetime.fromisoformat(error_data['alert_timestamp'].replace('Z', '+00:00'))
            date_folder = timestamp.strftime('%Y/%m/%d')
            time_folder = timestamp.strftime('%H')
            
            # Create S3 key with folder structure
            app_name = str(error_data.get('application_name', 'unknown'))
            s3_key = f"error-logs/{date_folder}/{time_folder}/{app_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            
            # Store the complete error data
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(error_data, indent=2),
                ContentType='application/json'
            )
            
            logger.info(f"Stored error data to S3: s3://{self.bucket_name}/{s3_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store error data to S3: {str(e)}")
            return False
    
    def retrieve_error_data(self, date: str, service_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve error data from S3 for a specific date and optionally service"""
        try:
            prefix = f"error-logs/{date}/"
            if service_name:
                prefix += f"*/{service_name}_*.json"
            else:
                prefix += "*/*.json"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix.replace('*', '')
            )
            
            error_data_list = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    try:
                        obj_response = self.s3_client.get_object(
                            Bucket=self.bucket_name,
                            Key=obj['Key']
                        )
                        content = obj_response['Body'].read().decode('utf-8')
                        error_data = json.loads(content)
                        error_data_list.append(error_data)
                    except Exception as e:
                        logger.warning(f"Failed to read object {obj['Key']}: {str(e)}")
            
            # Sort by timestamp descending
            error_data_list.sort(key=lambda x: x.get('alert_timestamp', ''), reverse=True)
            return error_data_list
            
        except Exception as e:
            logger.error(f"Failed to retrieve error data from S3: {str(e)}")
            return []

class LambdaService:
    """Service for invoking other Lambda functions"""
    
    def __init__(self):
        self.lambda_client = boto3.client('lambda')
        self.account_id = '681583877784'
        
    def invoke_dependent_services_lambda(self, function_name: str, app_name: str) -> List[str]:
        """Invoke Lambda to get dependent services"""
        try:
            payload = {'service_name': app_name}
            
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            response_payload = json.loads(response['Payload'].read())
            
            if 'errorMessage' in response_payload:
                raise Exception(f"Lambda function error: {response_payload['errorMessage']}")
            
            dependent_services = response_payload.get('dependent_services', [])
            
            if not isinstance(dependent_services, list):
                raise ValueError("Expected dependent_services to be a list")
            
            logger.info(f"Found {len(dependent_services)} dependent services")
            return dependent_services
            
        except Exception as e:
            logger.error(f"Error getting dependent services: {str(e)}")
            raise Exception(f"Failed to get dependent services: {str(e)}")
    
    def invoke_error_logs_lambda(self, function_name: str, service_names: List[str], 
                               error_timestamp: str) -> Dict[str, Any]:
        """Invoke Lambda to get error logs"""
        try:
            # Calculate 15 minutes before error timestamp
            error_time = datetime.fromisoformat(error_timestamp.replace('Z', '+00:00'))
            start_time = (error_time - timedelta(minutes=15)).isoformat()
            
            payload = {
                'service_names': service_names,
                'start_time': start_time,
                'end_time': error_timestamp
            }
            
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            response_payload = json.loads(response['Payload'].read())
            
            if 'errorMessage' in response_payload:
                raise Exception(f"Lambda function error: {response_payload['errorMessage']}")
            
            error_logs = response_payload.get('error_logs', {})
            
            if not isinstance(error_logs, dict):
                raise ValueError("Expected error_logs to be a dictionary")
            
            logger.info(f"Retrieved error logs for {len(error_logs)} services")
            return error_logs
            
        except Exception as e:
            logger.error(f"Error getting error logs: {str(e)}")
            raise Exception(f"Failed to get error logs: {str(e)}")

class WebhookProcessor:
    """Service for processing webhook payloads"""
    
    @staticmethod
    def parse_webhook_payload(event: Dict[str, Any]) -> tuple[str, str]:
        """Parse webhook payload to extract application name and timestamp"""
        if 'body' in event:
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                body = event['body']
        else:
            body = event
        
        if not isinstance(body, dict):
            raise ValueError("Invalid payload format. Expected JSON object.")
        
        app_name = body.get('application_name')
        timestamp = body.get('timestamp')
        
        if not app_name:
            raise ValueError("Missing required field: application_name")
        
        if not timestamp:
            raise ValueError("Missing required field: timestamp")
        
        # Validate and normalize timestamp
        try:
            # Try parsing ISO format first
            if 'T' in timestamp and 'Z' in timestamp:
                parsed_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                # Try parsing without timezone
                parsed_timestamp = datetime.fromisoformat(timestamp)
            
            # Convert back to ISO format for consistency
            timestamp = parsed_timestamp.isoformat()
            
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {timestamp}")
        
        return app_name, timestamp
    
    @staticmethod
    def create_error_response(app_name: str, timestamp: str, dependent_services: List[str], 
                            error_logs: Dict[str, Any]) -> Dict[str, Any]:
        """Create standardized error response"""
        return {
            'application_name': app_name,
            'alert_timestamp': timestamp,
            'dependent_services': dependent_services,
            'error_logs': error_logs,
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'failed_services': WebhookProcessor._identify_failed_services(error_logs),
            'service_hierarchy': WebhookProcessor._build_service_hierarchy(dependent_services, error_logs)
        }
    
    @staticmethod
    def _identify_failed_services(error_logs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify services with errors and extract error details"""
        failed_services = []
        
        for service_name, logs in error_logs.items():
            if logs and isinstance(logs, list):
                for log_entry in logs:
                    if isinstance(log_entry, dict) and log_entry.get('level') == 'ERROR':
                        failed_services.append({
                            'service_name': service_name,
                            'error_code': log_entry.get('error_code', 'UNKNOWN'),
                            'error_message': log_entry.get('message', 'Unknown error'),
                            'timestamp': log_entry.get('timestamp', '')
                        })
                        break  # Take first error per service
        
        return failed_services
    
    @staticmethod
    def _build_service_hierarchy(dependent_services: List[str], 
                               error_logs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build service hierarchy with error status"""
        hierarchy = []
        
        for service in dependent_services:
            service_logs = error_logs.get(service, [])
            has_errors = any(
                isinstance(log, dict) and log.get('level') == 'ERROR' 
                for log in service_logs
            )
            
            hierarchy.append({
                'service_name': service,
                'status': 'FAILED' if has_errors else 'HEALTHY',
                'error_count': len([log for log in service_logs 
                                  if isinstance(log, dict) and log.get('level') == 'ERROR'])
            })
        
        return hierarchy
