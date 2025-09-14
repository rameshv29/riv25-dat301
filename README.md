# DAT301 AI-Powered PostgreSQL Workshop

Enhanced workshop materials for the DAT301 session on AI-powered PostgreSQL incident detection using Amazon Bedrock AgentCore and CloudWatch MCP servers with transport wrapper architecture.

## 🚀 Quick Start

This repository contains enhanced workshop materials and MCP (Model Context Protocol) server implementations for the DAT301 workshop, featuring a production-ready transport wrapper approach using the official AWS Labs CloudWatch MCP server.

### Workshop Components

1. **Amazon Bedrock AgentCore Integration**
   - AI-powered database analysis
   - Natural language query interface
   - Automated incident detection

2. **CloudWatch MCP Server (Transport Wrapper)**
   - Uses official AWS Labs CloudWatch MCP server
   - HTTP transport wrapper for containerized deployment
   - Real-time metrics monitoring and log analysis
   - Production-ready with load balancer support

3. **Enhanced Workshop Environment**
   - Pre-configured VS Code Server
   - Docker-based MCP servers on ECS Fargate
   - Automated deployment with CloudFormation

## 📁 Repository Structure

```
├── assets/                     # Workshop assets and resources
├── cloudformation/             # CloudFormation templates
│   ├── mcp-servers-infrastructure.yaml
│   └── mcp-servers-services.yaml
├── docker/                     # Docker configurations
│   └── mcp-servers/           # MCP server implementations
│       └── cloudwatch-mcp/    # CloudWatch MCP transport wrapper
│           ├── Dockerfile     # Multi-stage build with AWS Labs MCP
│           ├── transport_wrapper.py  # HTTP transport wrapper
│           ├── health_check.py       # Container health checks
│           └── requirements.txt      # Python dependencies
├── docs/                      # Documentation
│   ├── architecture.md        # System architecture
│   └── deployment-guide.md    # Deployment instructions
├── scripts/                   # Deployment and utility scripts
│   ├── mcp-deployment/        # MCP server deployment scripts
│   └── workshop-utilities/    # Workshop utility scripts
└── README.md                  # This file
```

## 🏗️ Architecture

### Transport Wrapper Approach

```
┌─────────────────┐    ┌─────────────────────────────────────┐    ┌─────────────────┐
│   AI Agent      │───▶│         ECS Fargate Task            │───▶│  CloudWatch     │
│   (Bedrock)     │    │  ┌─────────────────────────────────┐ │    │  Metrics/Logs   │
│                 │    │  │    Transport Wrapper (Port 8000)│ │    │                 │
│                 │    │  │    ├─ FastAPI HTTP Server       │ │    │                 │
│                 │    │  │    ├─ Request Forwarding        │ │    │                 │
│                 │    │  │    └─ Health Checks             │ │    │                 │
│                 │    │  └─────────────────────────────────┘ │    │                 │
│                 │    │  ┌─────────────────────────────────┐ │    │                 │
│                 │    │  │  AWS Labs MCP Server (Port 3000)│ │    │                 │
│                 │    │  │    ├─ Official Implementation   │ │    │                 │
│                 │    │  │    ├─ CloudWatch Integration    │ │    │                 │
│                 │    │  │    └─ MCP Protocol Handler      │ │    │                 │
│                 │    │  └─────────────────────────────────┘ │    │                 │
└─────────────────┘    └─────────────────────────────────────┘    └─────────────────┘
                                        │
                                        ▼
                       ┌─────────────────────────────────────┐
                       │        Application Load Balancer    │
                       │  ├─ Health Checks (/health)         │
                       │  ├─ Path Routing (/mcp*)            │
                       │  └─ Auto Scaling Integration        │
                       └─────────────────────────────────────┘
```

## 🔧 Deployment

### Option 1: Complete Workshop Deployment

Deploy the full workshop with MCP servers using the enhanced CloudFormation template:

```bash
git clone https://github.com/rameshv29/riv25-dat301.git
cd riv25-dat301

# Deploy using the enhanced CloudFormation template
aws cloudformation deploy \
  --template-file corrected-enhanced-template.yaml \
  --stack-name dat301-workshop-enhanced \
  --parameter-overrides \
    WorkshopName=dat301-workshop \
    EnableGitHubEnhancements=yes \
    EnableMCPServers=yes \
    GitHubRepoUrl=https://github.com/rameshv29/riv25-dat301.git \
    DBUsername=workshop_admin \
    CodeEditorPassword=YourSecurePassword123! \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Option 2: MCP Servers Only

Deploy just the MCP servers infrastructure:

```bash
# Deploy infrastructure
aws cloudformation deploy \
  --template-file cloudformation/mcp-servers-infrastructure.yaml \
  --stack-name mcp-servers-infrastructure \
  --parameter-overrides \
    ProjectName=mcp-servers \
    Environment=dev \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Build and push Docker image
./scripts/mcp-deployment/build-cloudwatch-mcp.sh

# Deploy services
aws cloudformation deploy \
  --template-file cloudformation/mcp-servers-services.yaml \
  --stack-name mcp-servers-services \
  --parameter-overrides \
    ProjectName=mcp-servers \
    Environment=dev \
    ECSClusterName=mcp-servers-dev-cluster \
    CloudWatchMCPImageURI=ACCOUNT.dkr.ecr.REGION.amazonaws.com/mcp-servers/dev/cloudwatch-mcp-server:latest \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Option 3: Workshop Studio Environment

For AWS Workshop Studio deployments:

```bash
aws cloudformation deploy \
  --template-file corrected-enhanced-template.yaml \
  --stack-name dat301-workshop-studio \
  --parameter-overrides \
    WorkshopName=dat301-workshop \
    IsWorkshopStudioEnv=yes \
    EnableMCPServers=yes \
    ParticipantRoleArn=arn:aws:iam::ACCOUNT:role/WSParticipantRole \
    AssetsBucketName=your-workshop-assets-bucket \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

## 📊 MCP Servers

### CloudWatch MCP Server (Transport Wrapper)

Production-ready containerized MCP server with HTTP transport:

- **Endpoint**: `http://your-alb-dns/mcp`
- **Health Check**: `http://your-alb-dns/health`
- **Architecture**: Transport wrapper + AWS Labs MCP server
- **Deployment**: ECS Fargate with auto-scaling
- **Monitoring**: CloudWatch logs and metrics

#### Capabilities (via AWS Labs MCP Server)
- **CloudWatch Metrics**: Retrieve and analyze AWS CloudWatch metrics
- **CloudWatch Logs**: Access and filter CloudWatch log events  
- **RDS Performance**: Specialized RDS database performance metrics
- **Real-time Monitoring**: Live metrics and alerting
- **Multi-dimensional Analysis**: Complex metric queries and analysis

#### Transport Wrapper Features
- **HTTP Interface**: RESTful API for MCP protocol
- **Health Monitoring**: Built-in health checks for load balancers
- **Error Handling**: Robust error handling and logging
- **CORS Support**: Cross-origin request support
- **Auto-recovery**: Process management and restart capabilities

## 🔍 Features

### AI-Powered Analysis
- Natural language database queries using Bedrock AgentCore
- Automated performance analysis and recommendations
- Incident detection with contextual insights
- Integration with AWS services through MCP protocol

### Real-time Monitoring
- CloudWatch metrics integration via official AWS Labs server
- Advanced log analysis and filtering capabilities
- Performance insights with historical trending
- Automated alerting and notification systems

### Production-Ready Infrastructure
- ECS Fargate deployment with auto-scaling
- Application Load Balancer with health checks
- Multi-AZ deployment for high availability
- CloudWatch monitoring and logging
- Security groups and IAM roles following best practices

### Transport Wrapper Benefits
- **Reliability**: Uses official AWS Labs MCP implementation
- **Scalability**: HTTP transport suitable for load balancers
- **Maintainability**: Separation of transport and MCP logic
- **Monitoring**: Built-in health checks and observability
- **Security**: Proper error handling without exposing internals

## 📚 Documentation

- [Architecture Overview](docs/architecture.md) - Detailed system architecture
- [Deployment Guide](docs/deployment-guide.md) - Step-by-step deployment instructions
- [CloudWatch MCP Server](docker/mcp-servers/cloudwatch-mcp/README.md) - Transport wrapper documentation

## 🛠️ Development

### Local Development

```bash
# Clone repository
git clone https://github.com/rameshv29/riv25-dat301.git
cd riv25-dat301

# Build and test MCP server locally
cd docker/mcp-servers/cloudwatch-mcp
docker build -t cloudwatch-mcp-server .
docker run -p 8000:8000 -e AWS_DEFAULT_REGION=us-east-1 cloudwatch-mcp-server

# Test endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}'
```

### Testing MCP Integration

```bash
# Test with proper MCP headers
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly (including local Docker builds)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Submit a pull request

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_PORT` | `8000` | Transport wrapper port |
| `MCP_HOST` | `0.0.0.0` | Transport wrapper host |
| `AWS_DEFAULT_REGION` | `us-east-1` | AWS region for CloudWatch |

### CloudFormation Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `EnableMCPServers` | `yes` | Enable MCP servers deployment |
| `ProjectName` | `mcp-servers` | Resource naming prefix |
| `Environment` | `dev` | Environment name |
| `TaskCpu` | `512` | ECS task CPU units |
| `TaskMemory` | `1024` | ECS task memory (MB) |

## 🔍 Monitoring and Troubleshooting

### Health Checks

```bash
# Check service health
curl http://your-alb-dns/health

# Check ECS service status
aws ecs describe-services \
  --cluster your-cluster-name \
  --services your-service-name
```

### Logs

```bash
# View container logs
aws logs get-log-events \
  --log-group-name "/ecs/your-project/your-environment/cloudwatch-mcp" \
  --log-stream-name "ecs/cloudwatch-mcp-server/TASK_ID"
```

### Common Issues

1. **Container Health Check Failures**: Check AWS credentials and permissions
2. **MCP Server Not Starting**: Verify AWS Labs MCP server installation
3. **Transport Wrapper Errors**: Check port conflicts and network configuration

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Support

For questions or issues:
- Create an issue in this repository
- Review the [deployment guide](docs/deployment-guide.md)
- Check the [architecture documentation](docs/architecture.md)
- Contact the workshop team

## 🔄 Updates

This repository is actively maintained with:
- Regular security updates
- AWS Labs MCP server version updates
- Feature enhancements and bug fixes
- Documentation improvements
- CloudFormation template optimizations

Stay updated by watching this repository for changes.

## 🙏 Acknowledgments

- AWS Labs team for the official CloudWatch MCP server implementation
- Amazon Bedrock AgentCore team for AI integration capabilities
- Workshop participants for feedback and contributions