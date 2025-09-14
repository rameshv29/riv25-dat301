# CloudWatch MCP Server - Transport Wrapper

A containerized transport wrapper for the AWS Labs CloudWatch MCP server, providing HTTP access to CloudWatch metrics and logs for AI-powered database monitoring and analysis.

## 🚀 Features

- **AWS Labs Integration**: Uses the official AWS Labs CloudWatch MCP server
- **HTTP Transport**: Provides HTTP/REST interface for the MCP protocol
- **CloudWatch Metrics**: Full access to AWS CloudWatch metrics via AWS Labs server
- **CloudWatch Logs**: Complete CloudWatch logs access through AWS Labs server
- **Load Balancer Ready**: Designed for deployment behind AWS Application Load Balancer
- **Health Checks**: Built-in health monitoring for container orchestration
- **Auto-scaling**: Supports ECS Fargate auto-scaling

## 🏗️ Architecture

```
Transport Wrapper Architecture
├── FastAPI Transport Wrapper (Port 8000)
│   ├── HTTP Endpoints (/mcp, /health)
│   └── Request Forwarding
├── AWS Labs CloudWatch MCP Server (Port 3000)
│   ├── MCP Protocol Implementation
│   ├── CloudWatch Metrics Client
│   └── CloudWatch Logs Client
└── Health Monitoring & Load Balancer Integration
```

## 📋 Available Tools

This wrapper provides access to all AWS Labs CloudWatch MCP server tools:

### CloudWatch Metrics Tools
- **get_cloudwatch_metrics**: Retrieve CloudWatch metrics
- **list_cloudwatch_metrics**: List available metrics
- **get_metric_statistics**: Get detailed metric statistics

### CloudWatch Logs Tools  
- **get_cloudwatch_logs**: Access CloudWatch log events
- **list_log_groups**: List available log groups
- **filter_log_events**: Filter and search log events

### RDS Specific Tools
- **get_rds_performance_metrics**: Comprehensive RDS performance data
- **get_rds_slow_query_logs**: RDS slow query analysis

*Note: Exact tool names and parameters depend on the AWS Labs MCP server version. Refer to the [AWS Labs MCP Server documentation](https://github.com/awslabs/mcp-server-aws) for complete details.*

## 📋 Available Tools

### 1. get_cloudwatch_metrics
Get CloudWatch metrics for monitoring AWS resources.

**Parameters:**
- `namespace` (required): CloudWatch namespace (e.g., AWS/RDS, AWS/EC2)
- `metric_name` (required): Name of the metric to retrieve
- `dimensions` (optional): Dimensions to filter the metric
- `start_time` (optional): Start time in ISO format
- `end_time` (optional): End time in ISO format
- `period` (optional): Period in seconds (default: 300)

### 2. get_cloudwatch_logs
Get CloudWatch logs for troubleshooting and analysis.

**Parameters:**
- `log_group` (required): CloudWatch log group name
- `start_time` (optional): Start time in ISO format
- `end_time` (optional): End time in ISO format
- `filter_pattern` (optional): Filter pattern for log events
- `limit` (optional): Maximum number of log events (default: 100)

### 3. get_rds_performance_metrics
Get comprehensive RDS performance metrics for database analysis.

**Parameters:**
- `db_instance_identifier` (required): RDS database instance identifier
- `time_range_hours` (optional): Time range in hours (default: 1)

### 4. list_cloudwatch_metrics
List available CloudWatch metrics.

**Parameters:**
- `namespace` (optional): CloudWatch namespace to filter by

### 5. list_log_groups
List available CloudWatch log groups.

**Parameters:**
- `prefix` (optional): Log group name prefix to filter by

## 🔧 Configuration

### Environment Variables

- `MCP_PORT`: Server port (default: 8000)
- `MCP_HOST`: Server host (default: 0.0.0.0)
- `AWS_DEFAULT_REGION`: AWS region (default: us-east-1)

### AWS Permissions

The server requires the following AWS permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "cloudwatch:GetMetricStatistics",
                "cloudwatch:ListMetrics",
                "logs:FilterLogEvents",
                "logs:DescribeLogGroups"
            ],
            "Resource": "*"
        }
    ]
}
```

## 🚀 Usage

### Docker Deployment

```bash
# Build the image
docker build -t cloudwatch-mcp-server .

# Run the container
docker run -d \
  --name cloudwatch-mcp \
  -p 8000:8000 \
  -e AWS_DEFAULT_REGION=us-east-1 \
  cloudwatch-mcp-server
```

### Health Checks

- **General Health**: `GET /health`
- **CloudWatch Health**: `GET /cloudwatch/health`

### MCP Endpoints

- **List Tools**: `POST /mcp/tools/list`
- **Call Tool**: `POST /mcp/tools/call`

## 📊 Example Usage

### Get RDS CPU Utilization

```bash
curl -X POST http://localhost:8000/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_cloudwatch_metrics",
    "arguments": {
      "namespace": "AWS/RDS",
      "metric_name": "CPUUtilization",
      "dimensions": {
        "DBInstanceIdentifier": "my-database"
      }
    }
  }'
```

### Get Database Logs

```bash
curl -X POST http://localhost:8000/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_cloudwatch_logs",
    "arguments": {
      "log_group": "/aws/rds/instance/my-database/postgresql",
      "filter_pattern": "ERROR"
    }
  }'
```

## 🔍 Monitoring

The server provides structured JSON logging and Prometheus metrics for monitoring:

- Request/response logging
- Error tracking
- Performance metrics
- Health status

## 🛠️ Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python -m src.main
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src
```

## 📝 License

This project is licensed under the MIT License.