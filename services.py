import json
import boto3
import requests
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
    def parse_newrelic_alert(event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse New Relic alert payload to extract service details"""
        if 'body' in event:
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                body = event['body']
        else:
            body = event
        
        if not isinstance(body, dict):
            raise ValueError("Invalid payload format. Expected JSON object.")
        
        # Extract New Relic alert data
        service_name = body.get('service_name') or body.get('application_name') or body.get('entity_name')
        error_code = body.get('error_code') or body.get('status_code')
        endpoint = body.get('endpoint') or body.get('url') or body.get('path')
        timestamp = body.get('timestamp') or body.get('openedAt') or datetime.now(timezone.utc).isoformat()
        
        if not service_name:
            raise ValueError("Missing required field: service_name/application_name/entity_name")
        
        # Validate and normalize timestamp
        try:
            if 'T' in timestamp and ('Z' in timestamp or '+' in timestamp):
                parsed_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                parsed_timestamp = datetime.fromisoformat(timestamp)
            timestamp = parsed_timestamp.isoformat()
        except ValueError:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        return {
            'service_name': service_name,
            'error_code': error_code,
            'endpoint': endpoint,
            'timestamp': timestamp,
            'raw_payload': body
        }
    
    @staticmethod
    def calculate_start_time(end_time: str, minutes_before: int = 15) -> str:
        """Calculate start time by subtracting minutes from end time"""
        try:
            end_timestamp = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            start_timestamp = end_timestamp - timedelta(minutes=minutes_before)
            return start_timestamp.isoformat()
        except ValueError:
            # Fallback to current time if parsing fails
            return (datetime.now(timezone.utc) - timedelta(minutes=minutes_before)).isoformat()
    
    @staticmethod
    def create_rca_response(alert_data: Dict[str, Any], knowledge_result: Dict[str, Any], 
                           log_result: Dict[str, Any], rca_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive RCA response combining all results"""
        return {
            'alert_info': {
                'service_name': alert_data['service_name'],
                'error_code': alert_data['error_code'],
                'endpoint': alert_data['endpoint'],
                'alert_timestamp': alert_data['timestamp']
            },
            'knowledge_analysis': {
                'dependencies': knowledge_result.get('dependencies', {}),
                'past_incidents': knowledge_result.get('past_incidents', []),
                'analysis_timestamp': knowledge_result.get('analysis_timestamp')
            },
            'log_analysis': {
                'primary_service_logs': log_result.get('primary_service_logs', []),
                'related_service_logs': log_result.get('related_service_logs', []),
                'total_error_logs': log_result.get('total_error_logs', 0),
                'fetch_timestamp': log_result.get('fetch_timestamp')
            },
            'rca_summary': rca_summary.get('rca_summary', {}),
            'ongoing_errors': rca_summary.get('ongoing_errors', []),
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'dashboard_data': {
                'failed_services': WebhookProcessor._extract_failed_services(rca_summary),
                'impacted_endpoints': WebhookProcessor._extract_impacted_endpoints(rca_summary),
                'severity': WebhookProcessor._extract_severity(rca_summary),
                'business_impact': WebhookProcessor._extract_business_impact(rca_summary)
            }
        }
    
    @staticmethod
    def _extract_failed_services(rca_summary: Dict[str, Any]) -> List[str]:
        """Extract failed services from RCA summary"""
        rca_data = rca_summary.get('rca_summary', {})
        return rca_data.get('impacted_dependencies', [])
    
    @staticmethod
    def _extract_impacted_endpoints(rca_summary: Dict[str, Any]) -> List[str]:
        """Extract impacted endpoints from RCA summary"""
        rca_data = rca_summary.get('rca_summary', {})
        return rca_data.get('endpoints', [])
    
    @staticmethod
    def _extract_severity(rca_summary: Dict[str, Any]) -> str:
        """Extract severity from RCA summary"""
        rca_data = rca_summary.get('rca_summary', {})
        return rca_data.get('severity', 'Unknown')
    
    @staticmethod
    def _extract_business_impact(rca_summary: Dict[str, Any]) -> str:
        """Extract business impact from RCA summary"""
        rca_data = rca_summary.get('rca_summary', {})
        return rca_data.get('business_impact', 'Not specified')
    
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

class RCABotService:
    """Service for integrating with RCA Bot API"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
    def extract_document(self, service_name: str) -> Dict[str, Any]:
        """Call RCA bot document extraction service"""
        try:
            url = f"{self.base_url}/extract-document"
            payload = {"service_name": service_name}
            
            logger.info(f"Calling RCA bot document extraction for service: {service_name}")
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Successfully extracted document data for {service_name}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling RCA bot document extraction: {str(e)}")
            raise Exception(f"Failed to extract document data: {str(e)}")
    
    def fetch_logs(self, service_name: str, start_time: str, end_time: str) -> Dict[str, Any]:
        """Call RCA bot log fetching service"""
        try:
            url = f"{self.base_url}/fetch-logs"
            payload = {
                "service_name": service_name,
                "start_time": start_time,
                "end_time": end_time
            }
            
            logger.info(f"Calling RCA bot log fetching for service: {service_name}")
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Successfully fetched logs for {service_name}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling RCA bot log fetching: {str(e)}")
            raise Exception(f"Failed to fetch logs: {str(e)}")
    
    def train_analyze(self, service_name: str, document_data: Dict[str, Any], 
                     log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Call RCA bot training and analysis service"""
        try:
            url = f"{self.base_url}/train-analyze"
            payload = {
                "service_name": service_name,
                "document_data": document_data,
                "log_data": log_data
            }
            
            logger.info(f"Calling RCA bot training and analysis for service: {service_name}")
            response = self.session.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Successfully completed RCA analysis for {service_name}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling RCA bot training and analysis: {str(e)}")
            raise Exception(f"Failed to complete RCA analysis: {str(e)}")
    
    def complete_flow(self, service_name: str, start_time: str, end_time: str) -> Dict[str, Any]:
        """Call RCA bot complete flow service"""
        try:
            url = f"{self.base_url}/complete-flow"
            payload = {
                "service_name": service_name,
                "start_time": start_time,
                "end_time": end_time
            }
            
            logger.info(f"Calling RCA bot complete flow for service: {service_name}")
            response = self.session.post(url, json=payload, timeout=90)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Successfully completed RCA flow for {service_name}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling RCA bot complete flow: {str(e)}")
            raise Exception(f"Failed to complete RCA flow: {str(e)}")
    
    def health_check(self) -> Dict[str, Any]:
        """Check RCA bot health"""
        try:
            url = f"{self.base_url}/health"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"RCA bot health check failed: {str(e)}")
            return {"status": "unhealthy", "error": str(e)}
