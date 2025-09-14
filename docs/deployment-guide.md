# DAT301 Workshop Deployment Guide

## 🚀 Quick Start

This guide covers deploying the complete DAT301 AI-Powered PostgreSQL Workshop with MCP servers integration.

## 📋 Prerequisites

### AWS Account Requirements
- AWS CLI configured with appropriate permissions
- Docker installed (for building MCP server images)
- Git installed
- Sufficient AWS service limits:
  - VPC: 1 (or use existing)
  - EC2 instances: 1 (t4g.xlarge or larger)
  - ECS clusters: 1
  - Application Load Balancers: 1
  - Aurora PostgreSQL clusters: 1

### Required AWS Permissions
The deployment requires permissions for:
- CloudFormation (full access)
- EC2 (VPC, instances, security groups)
- ECS (clusters, services, tasks)
- ECR (repositories, images)
- RDS (Aurora PostgreSQL)
- IAM (roles, policies)
- CloudWatch (logs, metrics)
- Secrets Manager
- Elastic Load Balancing v2

## 🏗️ Deployment Options

### Option 1: Complete Workshop with MCP Servers (Recommended)

Deploy the full workshop including AI-powered monitoring capabilities.

```bash
# Clone the repository
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

### Option 2: Workshop Studio Environment

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

### Option 3: MCP Servers Only

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

# Build and deploy MCP server images
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

## 🔧 Configuration Parameters

### Core Workshop Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WorkshopName` | `ai-postgresql-workshop` | Workshop identifier |
| `WorkshopAuthor` | `Ramesh Kumar Venkatraman` | Workshop author |
| `DBUsername` | `workshop_admin` | Database admin username |
| `DBName` | `workshop_db` | Database name |
| `EnablePgVector` | `yes` | Enable pgvector extension |

### Code Editor Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CodeEditorInstanceType` | `t4g.xlarge` | EC2 instance type |
| `InstanceVolumeSize` | `80` | EBS volume size (GB) |
| `CodeEditorUser` | `workshop` | VS Code username |
| `CodeEditorPassword` | `61V25Workshop!` | VS Code password |

### GitHub Integration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `GitHubRepoUrl` | `https://github.com/rameshv29/riv25-dat301.git` | Repository URL |
| `GitHubBranch` | `main` | Branch to clone |
| `EnableGitHubEnhancements` | `yes` | Enable GitHub integration |

### MCP Servers Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `EnableMCPServers` | `yes` | Enable MCP servers deployment |
| `ProjectName` | `mcp-servers` | MCP resource naming prefix |
| `Environment` | `dev` | Environment name |
| `CloudWatchMCPPort` | `8000` | MCP server port |

### Workshop Studio Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `IsWorkshopStudioEnv` | `no` | Workshop Studio environment |
| `AssetsBucketName` | `''` | S3 assets bucket |
| `ParticipantRoleArn` | `''` | Participant role ARN |

## 📊 Deployment Monitoring

### CloudFormation Stack Events

Monitor deployment progress:

```bash
# Watch stack events
aws cloudformation describe-stack-events \
  --stack-name dat301-workshop-enhanced \
  --region us-east-1 \
  --query 'StackEvents[*].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId]' \
  --output table

# Check stack status
aws cloudformation describe-stacks \
  --stack-name dat301-workshop-enhanced \
  --region us-east-1 \
  --query 'Stacks[0].StackStatus'
```

### ECS Service Health

Monitor MCP server deployment:

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster dat301-workshop-mcp-cluster \
  --services dat301-workshop-cloudwatch-mcp-service \
  --region us-east-1 \
  --query 'services[0].[serviceName,status,runningCount,desiredCount]'

# Check task health
aws ecs list-tasks \
  --cluster dat301-workshop-mcp-cluster \
  --service-name dat301-workshop-cloudwatch-mcp-service \
  --region us-east-1
```

### Application Health Checks

Verify services are running:

```bash
# Get ALB DNS name
ALB_DNS=$(aws cloudformation describe-stacks \
  --stack-name dat301-workshop-enhanced \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`MCPServersALBDNS`].OutputValue' \
  --output text)

# Test health endpoints
curl -f http://$ALB_DNS/health
curl -f http://$ALB_DNS/mcp -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

## 🔍 Troubleshooting

### Common Issues

#### 1. CloudFormation Stack Creation Failed

**Symptoms**: Stack creation fails with resource errors

**Solutions**:
- Check AWS service limits
- Verify IAM permissions
- Review CloudFormation events for specific errors
- Ensure unique resource names

```bash
# Check failed resources
aws cloudformation describe-stack-events \
  --stack-name dat301-workshop-enhanced \
  --region us-east-1 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```

#### 2. ECS Tasks Not Starting

**Symptoms**: ECS service shows 0 running tasks

**Solutions**:
- Check task definition configuration
- Verify ECR image exists and is accessible
- Review ECS task logs
- Check security group rules

```bash
# Check task failures
aws ecs describe-tasks \
  --cluster dat301-workshop-mcp-cluster \
  --tasks $(aws ecs list-tasks --cluster dat301-workshop-mcp-cluster --service-name dat301-workshop-cloudwatch-mcp-service --query 'taskArns[0]' --output text) \
  --region us-east-1
```

#### 3. Docker Build Failures

**Symptoms**: MCP server image build fails

**Solutions**:
- Ensure Docker is running
- Check ECR permissions
- Verify network connectivity
- Review build logs

```bash
# Manual build and push
cd docker/mcp-servers/cloudwatch-mcp
docker build -t cloudwatch-mcp-server .

# Test locally
docker run -p 8000:8000 cloudwatch-mcp-server
curl http://localhost:8000/health
```

#### 4. Health Check Failures

**Symptoms**: ALB health checks failing

**Solutions**:
- Verify container port configuration
- Check security group rules
- Review application logs
- Test health endpoint directly

```bash
# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws cloudformation describe-stacks \
    --stack-name dat301-workshop-enhanced \
    --region us-east-1 \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudWatchMCPTargetGroup`].OutputValue' \
    --output text) \
  --region us-east-1
```

### Log Analysis

#### CloudWatch Logs

```bash
# View ECS task logs
aws logs get-log-events \
  --log-group-name "/ecs/dat301-workshop/mcp-servers/cloudwatch-mcp" \
  --log-stream-name "ecs/cloudwatch-mcp-server/TASK_ID" \
  --region us-east-1
```

#### EC2 Instance Logs

```bash
# SSH to EC2 instance (if accessible)
ssh -i your-key.pem ec2-user@INSTANCE_IP

# Check cloud-init logs
sudo tail -f /var/log/cloud-init-output.log

# Check workshop setup logs
sudo tail -f /var/log/workshop-setup.log
```

## 🧹 Cleanup

### Complete Cleanup

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack \
  --stack-name dat301-workshop-enhanced \
  --region us-east-1

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete \
  --stack-name dat301-workshop-enhanced \
  --region us-east-1

# Clean up ECR images (optional)
aws ecr list-images \
  --repository-name dat301-workshop/cloudwatch-mcp-server \
  --region us-east-1 \
  --query 'imageIds[*]' \
  --output json | \
aws ecr batch-delete-image \
  --repository-name dat301-workshop/cloudwatch-mcp-server \
  --region us-east-1 \
  --image-ids file:///dev/stdin
```

### Selective Cleanup

```bash
# Delete only MCP servers
aws cloudformation delete-stack \
  --stack-name mcp-servers-services \
  --region us-east-1

aws cloudformation delete-stack \
  --stack-name mcp-servers-infrastructure \
  --region us-east-1
```

## 📚 Next Steps

After successful deployment:

1. **Access the Workshop**:
   - Get the Code Editor URL from CloudFormation outputs
   - Log in with configured credentials
   - Start exploring the workshop materials

2. **Test MCP Integration**:
   - Verify MCP server endpoints are accessible
   - Test CloudWatch metrics retrieval
   - Explore AI-powered database analysis

3. **Customize Configuration**:
   - Modify workshop parameters as needed
   - Add additional MCP servers
   - Integrate with existing AWS infrastructure

4. **Monitor and Maintain**:
   - Set up CloudWatch alarms
   - Review logs regularly
   - Update images and configurations as needed

For detailed usage instructions, see the workshop documentation in the Code Editor environment.