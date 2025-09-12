# CloudWatch MCP Server

A Model Context Protocol (MCP) server that provides CloudWatch metrics and logs access for AI-powered database monitoring and analysis.

## 🚀 Features

- **CloudWatch Metrics**: Retrieve and analyze AWS CloudWatch metrics
- **CloudWatch Logs**: Access and filter CloudWatch log events
- **RDS Performance**: Specialized RDS database performance metrics
- **MCP Protocol**: Full Model Context Protocol implementation
- **Health Checks**: Built-in health monitoring and diagnostics

## 🏗️ Architecture

```
CloudWatch MCP Server
├── FastAPI Web Server (Port 8000)
├── MCP Protocol Handler
├── CloudWatch Tools
│   ├── Metrics Client
│   └── Logs Client
└── Health Monitoring
```

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