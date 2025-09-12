# DAT301 Workshop Architecture

## 🏗️ Overview

The DAT301 AI-Powered PostgreSQL Workshop combines Amazon Bedrock AgentCore with CloudWatch MCP servers to demonstrate AI-powered database monitoring and incident detection.

## 📐 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                Workshop Studio                                   │
│  ┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐ │
│  │   Participant       │    │   CloudFormation     │    │   GitHub Repository │ │
│  │   Interface         │    │   Template           │    │   (Enhancements)    │ │
│  └─────────────────────┘    └──────────────────────┘    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AWS Account (Workshop)                             │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                                VPC                                          │ │
│  │                                                                             │ │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐ │ │
│  │  │  Public Subnet  │    │  Public Subnet  │    │    Private Subnet       │ │ │
│  │  │                 │    │                 │    │                         │ │ │
│  │  │  ┌───────────┐  │    │  ┌───────────┐  │    │  ┌─────────────────────┐ │ │ │
│  │  │  │Code Editor│  │    │  │    ALB    │  │    │  │   Aurora PostgreSQL │ │ │ │
│  │  │  │(VS Code)  │  │    │  │           │  │    │  │   with pgvector     │ │ │ │
│  │  │  │           │  │    │  └───────────┘  │    │  └─────────────────────┘ │ │ │
│  │  │  └───────────┘  │    │                 │    │                         │ │ │
│  │  │                 │    │                 │    │  ┌─────────────────────┐ │ │ │
│  │  └─────────────────┘    └─────────────────┘    │  │   ECS Fargate       │ │ │ │
│  │                                                 │  │   (MCP Servers)     │ │ │ │
│  │                                                 │  └─────────────────────┘ │ │ │
│  │                                                 └─────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                            AWS Services                                     │ │
│  │                                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │ │
│  │  │   Bedrock   │  │ CloudWatch  │  │   Secrets   │  │        ECR          │ │ │
│  │  │ AgentCore   │  │   Metrics   │  │   Manager   │  │   (Docker Images)   │ │ │
│  │  │             │  │    Logs     │  │             │  │                     │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 🔧 Components

### Core Workshop Components

#### 1. **Amazon Bedrock AgentCore**
- **Purpose**: AI-powered database analysis and incident detection
- **Location**: `/tmp/amazon-bedrock-agentcore-samples/02-use-cases/DB-performance-analyzer`
- **Features**:
  - Natural language database queries
  - Automated performance analysis
  - Incident detection and recommendations
  - Integration with AWS services

#### 2. **Aurora PostgreSQL with pgvector**
- **Purpose**: Workshop database with AI/ML capabilities
- **Configuration**:
  - Engine: `aurora-postgresql` (version 15.4)
  - Scaling: Serverless v2 (0.5-4 ACU)
  - Extensions: pgvector for vector operations
  - Performance Insights enabled

#### 3. **VS Code Server**
- **Purpose**: Interactive development environment
- **Access**: Web-based IDE on port 8080
- **Features**:
  - Pre-configured Python environment
  - Database connectivity tools
  - Workshop notebooks and examples

### Enhanced Components (GitHub Integration)

#### 4. **CloudWatch MCP Server**
- **Purpose**: Model Context Protocol server for CloudWatch integration
- **Technology**: FastAPI + Docker + ECS Fargate
- **Capabilities**:
  - CloudWatch metrics retrieval
  - Log analysis and filtering
  - RDS performance monitoring
  - Real-time health checks

#### 5. **Application Load Balancer**
- **Purpose**: Route traffic to MCP servers
- **Configuration**:
  - Internet-facing ALB
  - Health checks on `/health` endpoint
  - Path-based routing for MCP endpoints

#### 6. **ECS Infrastructure**
- **Purpose**: Container orchestration for MCP servers
- **Configuration**:
  - Fargate launch type
  - Auto-scaling capabilities
  - CloudWatch logging integration
  - Service discovery

## 🔄 Data Flow

### 1. **Workshop Initialization**
```
CloudFormation → EC2 Instance → AgentCore Setup → Database Connection
```

### 2. **GitHub Integration Flow**
```
EC2 Instance → Clone GitHub Repo → Build Docker Images → Deploy to ECS
```

### 3. **AI Analysis Flow**
```
User Query → AgentCore → Database Analysis → CloudWatch MCP → Metrics/Logs → AI Insights
```

### 4. **Monitoring Flow**
```
Database → CloudWatch → MCP Server → AgentCore → AI Analysis → Recommendations
```

## 🔐 Security Architecture

### Network Security
- **VPC Isolation**: All resources in dedicated VPC
- **Security Groups**: Least-privilege access rules
- **Private Subnets**: Database and ECS tasks in private subnets
- **NAT Gateways**: Outbound internet access for private resources

### Access Control
- **IAM Roles**: Service-specific roles with minimal permissions
- **Secrets Manager**: Secure credential storage
- **Instance Profiles**: EC2 access to AWS services
- **Task Roles**: ECS task-specific permissions

### Data Protection
- **Encryption at Rest**: RDS encryption enabled
- **Encryption in Transit**: TLS for all communications
- **Secret Rotation**: Automated credential management
- **Audit Logging**: CloudTrail and CloudWatch logs

## 📊 Monitoring and Observability

### Application Monitoring
- **CloudWatch Metrics**: Custom metrics from MCP servers
- **CloudWatch Logs**: Structured logging from all components
- **Performance Insights**: Database performance monitoring
- **Container Insights**: ECS task and service metrics

### Health Checks
- **ALB Health Checks**: HTTP health endpoints
- **ECS Health Checks**: Container-level health monitoring
- **Database Health**: Connection and performance monitoring
- **Workshop Validation**: Automated setup verification

## 🚀 Deployment Architecture

### Phase 1: Infrastructure
1. **VPC and Networking**: Subnets, gateways, security groups
2. **Database**: Aurora PostgreSQL cluster and instance
3. **ECS Infrastructure**: Cluster, ALB, target groups
4. **IAM Roles**: Service roles and policies

### Phase 2: Core Workshop
1. **EC2 Instance**: Code Editor with VS Code Server
2. **AgentCore Setup**: Clone and configure AgentCore samples
3. **Database Configuration**: Connection setup and initial data

### Phase 3: GitHub Integration (Optional)
1. **Repository Clone**: Download workshop enhancements
2. **Docker Build**: Build and push MCP server images
3. **Service Deployment**: Deploy MCP servers to ECS
4. **Validation**: Verify complete setup

## 🔧 Configuration Management

### Environment Variables
- **AWS_REGION**: Target AWS region
- **PROJECT_NAME**: Resource naming prefix
- **ENVIRONMENT**: Deployment environment (dev/staging/prod)
- **GITHUB_REPO_URL**: Workshop enhancements repository
- **ENABLE_GITHUB_ENHANCEMENTS**: Feature flag for GitHub integration

### Parameter Store
- **Database Configuration**: Connection parameters
- **MCP Configuration**: Server endpoints and settings
- **Workshop Settings**: User preferences and configurations

### Secrets Manager
- **Database Credentials**: Auto-generated master password
- **AgentCore Configuration**: API keys and settings
- **Application Secrets**: Service-to-service authentication

## 📈 Scalability Considerations

### Horizontal Scaling
- **ECS Auto Scaling**: Automatic task scaling based on metrics
- **Database Scaling**: Aurora Serverless v2 automatic scaling
- **Load Balancer**: Distributes traffic across multiple tasks

### Vertical Scaling
- **Instance Types**: Configurable EC2 instance sizes
- **Task Resources**: Adjustable CPU and memory allocation
- **Database Capacity**: Configurable ACU limits

### Performance Optimization
- **Connection Pooling**: Efficient database connections
- **Caching**: Application-level caching where appropriate
- **Resource Monitoring**: Continuous performance monitoring

## 🔄 Disaster Recovery

### Backup Strategy
- **Database Backups**: Automated Aurora backups (7-day retention)
- **Configuration Backup**: Infrastructure as Code (CloudFormation)
- **Code Backup**: Version control in GitHub

### Recovery Procedures
- **Point-in-Time Recovery**: Database restoration capabilities
- **Infrastructure Recovery**: CloudFormation stack recreation
- **Service Recovery**: ECS service auto-recovery

This architecture provides a robust, scalable, and secure foundation for the AI-powered PostgreSQL workshop while maintaining flexibility for enhancements and customizations.