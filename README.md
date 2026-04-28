# Logging Platform Webhook Handler

This AWS Lambda function handles webhook calls from a logging platform when alerts are triggered. It processes application alerts by retrieving dependent services and their error logs, storing the results in S3, and providing a monitoring dashboard.

## Enhanced Features

### S3 Storage
- **Date/Timestamp Folder Structure**: Error data is stored in S3 with organized folder structure: `error-logs/YYYY/MM/DD/HH/application_YYYYMMDD_HHMMSS.json`
- **Persistent Storage**: All error data is preserved for historical analysis and dashboard reporting
- **Automatic Organization**: Data is automatically organized by date and time for easy retrieval

### Monitoring Dashboard
- **Real-time Dashboard**: S3-hosted static website for monitoring errors
- **Service Flow Visualization**: Shows service hierarchy with error status
- **Error Timeline**: Chronological view of all errors with filtering capabilities
- **Interactive Details**: Click on any error to see detailed information including error codes and messages

### Modular Architecture
- **Service Classes**: Separated into `S3StorageService`, `LambdaService`, and `WebhookProcessor`
- **Clean Separation**: Each service handles a specific responsibility
- **Easy Testing**: Modular design enables comprehensive unit testing
- **Maintainable Code**: Clear structure for future enhancements

## Functionality

1. **Webhook Reception**: Receives application name and timestamp from logging platform webhook
2. **Dependency Discovery**: Calls a Lambda service to get all dependent services for the application
3. **Error Log Retrieval**: Calls another Lambda service to get error logs for all dependent services 15 minutes before the alert timestamp
4. **Error Analysis**: Identifies failed services, extracts error codes and messages
5. **S3 Storage**: Stores complete error data with organized folder structure
6. **Response Aggregation**: Returns consolidated data including dependent services and their error logs

## Architecture

```
Logging Platform → Webhook Lambda → Dependent Services Lambda → Error Logs Lambda → S3 Storage → Dashboard
```

## File Structure

```
├── lambda_webhook_handler.py    # Main Lambda function
├── services.py                  # Modular service classes
├── test_webhook_handler.py      # Comprehensive unit tests
├── requirements.txt             # Python dependencies
├── README.md                    # This documentation
└── dashboard/                   # Monitoring dashboard
    ├── index.html              # Dashboard HTML
    └── dashboard.js            # Dashboard JavaScript
```

## Configuration

### Environment Variables

- `DEPENDENT_SERVICES_LAMBDA`: Name/ARN of the Lambda function that returns dependent services (default: 'get-dependent-services')
- `ERROR_LOGS_LAMBDA`: Name/ARN of the Lambda function that returns error logs (default: 'get-error-logs')
- `S3_BUCKET_NAME`: Name of the S3 bucket for storing error data (default: 'error-monitoring-bucket')

### Expected Webhook Payload

```json
{
  "application_name": "my-app",
  "timestamp": "2024-04-28T10:30:00Z"
}
```

### Enhanced Response Format

```json
{
  "application_name": "my-app",
  "alert_timestamp": "2024-04-28T10:30:00Z",
  "dependent_services": ["service1", "service2", "service3"],
  "error_logs": {
    "service1": [
      {"level": "ERROR", "message": "Connection failed", "error_code": "CONN_ERROR", "timestamp": "2024-04-28T10:29:45Z"}
    ]
  },
  "failed_services": [
    {
      "service_name": "service1",
      "error_code": "CONN_ERROR",
      "error_message": "Connection failed",
      "timestamp": "2024-04-28T10:29:45Z"
    }
  ],
  "service_hierarchy": [
    {
      "service_name": "service1",
      "status": "FAILED",
      "error_count": 1
    }
  ],
  "processed_at": "2024-04-28T10:35:00.123456"
}
```

## Dependencies

### Dependent Services Lambda

**Input:**
```json
{
  "service_name": "application-name"
}
```

**Output:**
```json
{
  "dependent_services": ["service1", "service2", "service3"]
}
```

### Error Logs Lambda

**Input:**
```json
{
  "service_names": ["service1", "service2", "service3"],
  "start_time": "2024-04-28T10:15:00Z",
  "end_time": "2024-04-28T10:30:00Z"
}
```

**Output:**
```json
{
  "error_logs": {
    "service1": [
      {"level": "ERROR", "message": "Error details", "error_code": "ERR001", "timestamp": "2024-04-28T10:29:45Z"}
    ],
    "service2": [{"level": "INFO", "message": "Normal operation"}]
  }
}
```

## S3 Storage Structure

Error data is stored in S3 with the following folder structure:

```
error-logs/
├── 2024/
│   ├── 04/
│   │   ├── 28/
│   │   │   ├── 10/
│   │   │   │   ├── payment-service_20240428_103000.json
│   │   │   │   └── user-service_20240428_103015.json
│   │   │   └── 11/
│   │   │       └── order-service_20240428_110500.json
```

## Monitoring Dashboard

### Features
- **Real-time Updates**: Auto-refreshes every 30 seconds
- **Filtering**: Filter by date, service name, and status
- **Summary Cards**: Shows total alerts, failed services, healthy services, and error rate
- **Error Timeline**: Chronological view of all errors with visual indicators
- **Service Flow Analysis**: Detailed view of service hierarchies and error status
- **Interactive Details**: Click on any error to see complete information

### Dashboard Access

1. Deploy the dashboard files to an S3 bucket with static website hosting enabled
2. Configure the bucket policy for public access (or use CloudFront for restricted access)
3. Access the dashboard at the S3 website endpoint

### Dashboard Configuration

The dashboard can be configured with URL parameters:
- `?bucket=your-bucket-name` - Specify the S3 bucket name

## Deployment

### 1. Lambda Function Deployment

```bash
# Package the Lambda function
zip -r lambda-function.zip lambda_webhook_handler.py services.py requirements.txt

# Deploy to AWS
aws lambda create-function \
  --function-name error-webhook-handler \
  --runtime python3.9 \
  --role arn:aws:iam::681583877784:role/lambda-execution-role \
  --handler lambda_webhook_handler.lambda_handler \
  --zip-file fileb://lambda-function.zip \
  --environment Variables="{DEPENDENT_SERVICES_LAMBDA=get-dependent-services,ERROR_LOGS_LAMBDA=get-error-logs,S3_BUCKET_NAME=error-monitoring-bucket}"
```

### 2. S3 Bucket Setup

```bash
# Create S3 bucket
aws s3 mb s3://error-monitoring-bucket

# Enable static website hosting
aws s3 website s3://error-monitoring-bucket --index-document index.html

# Upload dashboard files
aws s3 sync dashboard/ s3://error-monitoring-bucket/

# Set bucket policy for public access
aws s3api put-bucket-policy --bucket error-monitoring-bucket --policy file://bucket-policy.json
```

### 3. API Gateway Setup

Configure API Gateway to trigger the Lambda function:
1. Create a new REST API
2. Add a POST method to the root resource
3. Set integration type to Lambda Function
4. Select the deployed Lambda function
5. Deploy the API to a stage

## IAM Permissions Required

### Lambda Function Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:*:681583877784:function:get-dependent-services",
        "arn:aws:lambda:*:681583877784:function:get-error-logs"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::error-monitoring-bucket",
        "arn:aws:s3:::error-monitoring-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

### S3 Bucket Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::error-monitoring-bucket/*"
    }
  ]
}
```

## Testing

### Unit Tests

Run comprehensive unit tests:

```bash
python -m pytest test_webhook_handler.py -v
```

### Local Testing

Test the Lambda function locally with mock AWS services:

```bash
python lambda_webhook_handler.py
```

This will:
- Mock all AWS service calls
- Test the complete workflow
- Display detailed results
- Verify S3 storage structure

### Integration Testing

Test the complete workflow:
1. Deploy all Lambda functions
2. Configure S3 bucket
3. Send test webhook payload
4. Verify S3 storage
5. Check dashboard display

## Error Handling

The function includes comprehensive error handling:
- Input validation for webhook payload
- Timestamp format validation
- Lambda function invocation error handling
- S3 storage error handling
- Structured logging for debugging
- Graceful degradation when S3 storage fails

## Monitoring and Alerting

### CloudWatch Metrics
- Lambda function invocations
- Lambda function errors
- Lambda function duration
- S3 storage operations

### CloudWatch Logs
- Detailed logging of all operations
- Error tracking and debugging information
- Performance metrics

### Dashboard Monitoring
- Real-time error visualization
- Service health monitoring
- Error trend analysis

## Security Considerations

- Use IAM roles with least privilege
- Enable VPC endpoints if required
- Implement API Gateway authentication if needed
- Use HTTPS for all communications
- Regularly rotate access keys
- Enable S3 bucket logging

## Performance Optimization

- Lambda function timeout: 30 seconds
- Memory allocation: 256 MB
- S3 storage optimized for query patterns
- Dashboard caching for improved performance
- Auto-refresh interval: 30 seconds

## Troubleshooting

### Common Issues

1. **Lambda Timeout**: Increase timeout or optimize dependent Lambda functions
2. **S3 Access**: Check IAM permissions and bucket policies
3. **Dashboard Not Loading**: Verify S3 static website hosting configuration
4. **Missing Data**: Check dependent Lambda function responses

### Debugging

- Check CloudWatch logs for detailed error information
- Use the local testing script for isolated testing
- Verify S3 bucket structure and permissions
- Test dependent Lambda functions independently

## Future Enhancements

- **Real-time Notifications**: Add SNS notifications for critical errors
- **Advanced Analytics**: Add error pattern analysis and prediction
- **Multi-region Support**: Deploy across multiple AWS regions
- **Authentication**: Add user authentication for dashboard access
- **Custom Alerts**: Configure custom alert thresholds and notifications
- **Export Functionality**: Add CSV/PDF export for error reports
- **Integration**: Add support for additional monitoring tools
