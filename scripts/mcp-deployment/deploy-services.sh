#!/bin/bash
set -euo pipefail

# MCP Services Deployment Script
# This script deploys MCP services to ECS using the built Docker images

echo "🚀 Starting MCP Services deployment..."

# Configuration
PROJECT_NAME=${PROJECT_NAME:-"mcp-servers"}
ENVIRONMENT=${ENVIRONMENT:-"dev"}
AWS_REGION=${AWS_REGION:-$(aws configure get region || echo "us-east-1")}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}

# ECS Configuration (these should match CloudFormation template)
ECS_CLUSTER=${ECS_CLUSTER:-"${PROJECT_NAME}-${ENVIRONMENT}-cluster"}
TASK_FAMILY="${PROJECT_NAME}-${ENVIRONMENT}-cloudwatch-mcp"
SERVICE_NAME="${PROJECT_NAME}-${ENVIRONMENT}-cloudwatch-mcp-service"

# ECR Configuration
ECR_REPO_NAME="${PROJECT_NAME}/${ENVIRONMENT}/cloudwatch-mcp-server"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "📋 Deployment Configuration:"
echo "  Project: ${PROJECT_NAME}"
echo "  Environment: ${ENVIRONMENT}"
echo "  AWS Region: ${AWS_REGION}"
echo "  ECS Cluster: ${ECS_CLUSTER}"
echo "  Task Family: ${TASK_FAMILY}"
echo "  Service Name: ${SERVICE_NAME}"
echo "  ECR URI: ${ECR_URI}"

# Get script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Load deployment info if available
DEPLOYMENT_INFO_FILE="${REPO_ROOT}/deployment-info.json"
if [ -f "${DEPLOYMENT_INFO_FILE}" ]; then
    echo "📄 Loading deployment information from ${DEPLOYMENT_INFO_FILE}"
    # You could parse JSON here if needed
fi

# Verify ECS cluster exists
echo "🔍 Verifying ECS cluster..."
if ! aws ecs describe-clusters --clusters "${ECS_CLUSTER}" --region "${AWS_REGION}" --query 'clusters[0].status' --output text | grep -q "ACTIVE"; then
    echo "❌ ECS cluster not found or not active: ${ECS_CLUSTER}"
    echo "   Make sure the CloudFormation stack has been deployed successfully"
    exit 1
fi
echo "✅ ECS cluster is active: ${ECS_CLUSTER}"

# Get existing task definition (if any)
echo "🔍 Checking existing task definition..."
EXISTING_TASK_DEF=""
if aws ecs describe-task-definition --task-definition "${TASK_FAMILY}" --region "${AWS_REGION}" >/dev/null 2>&1; then
    EXISTING_TASK_DEF=$(aws ecs describe-task-definition --task-definition "${TASK_FAMILY}" --region "${AWS_REGION}" --query 'taskDefinition.revision' --output text)
    echo "📋 Found existing task definition: ${TASK_FAMILY}:${EXISTING_TASK_DEF}"
else
    echo "📋 No existing task definition found, will create new one"
fi

# Get CloudFormation stack outputs for required resources
echo "🔍 Getting CloudFormation stack outputs..."
STACK_NAME="${PROJECT_NAME}-${ENVIRONMENT}"  # Adjust if your stack name is different

# Try to get stack outputs
if aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
    echo "📋 Found CloudFormation stack: ${STACK_NAME}"
    
    # Get required resources from stack outputs
    EXECUTION_ROLE_ARN=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`ECSTaskExecutionRoleArn`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    TASK_ROLE_ARN=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudWatchMCPTaskRoleArn`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    LOG_GROUP=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudWatchMCPLogGroup`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    PRIVATE_SUBNETS=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnets`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    SECURITY_GROUP=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`ECSSecurityGroup`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    TARGET_GROUP_ARN=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudWatchMCPTargetGroupArn`].OutputValue' \
        --output text 2>/dev/null || echo "")
else
    echo "⚠️ CloudFormation stack not found: ${STACK_NAME}"
    echo "   Will use environment variables or defaults"
fi

# Set defaults if not found in CloudFormation
EXECUTION_ROLE_ARN=${EXECUTION_ROLE_ARN:-${ECS_EXECUTION_ROLE_ARN:-""}}
TASK_ROLE_ARN=${TASK_ROLE_ARN:-${CLOUDWATCH_MCP_TASK_ROLE_ARN:-""}}
LOG_GROUP=${LOG_GROUP:-"/ecs/${PROJECT_NAME}/${ENVIRONMENT}/cloudwatch-mcp"}
PRIVATE_SUBNETS=${PRIVATE_SUBNETS:-${ECS_SUBNETS:-""}}
SECURITY_GROUP=${SECURITY_GROUP:-${ECS_SECURITY_GROUP:-""}}
TARGET_GROUP_ARN=${TARGET_GROUP_ARN:-${TARGET_GROUP_ARN:-""}}

# Validate required parameters
if [ -z "${EXECUTION_ROLE_ARN}" ]; then
    echo "❌ ECS Task Execution Role ARN not found"
    echo "   Set ECS_EXECUTION_ROLE_ARN environment variable or ensure CloudFormation stack outputs are available"
    exit 1
fi

if [ -z "${TASK_ROLE_ARN}" ]; then
    echo "❌ CloudWatch MCP Task Role ARN not found"
    echo "   Set CLOUDWATCH_MCP_TASK_ROLE_ARN environment variable or ensure CloudFormation stack outputs are available"
    exit 1
fi

echo "✅ Configuration validated"

# Create task definition JSON
echo "📝 Creating task definition..."
TASK_DEF_JSON=$(cat << EOF
{
    "family": "${TASK_FAMILY}",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "512",
    "memory": "1024",
    "executionRoleArn": "${EXECUTION_ROLE_ARN}",
    "taskRoleArn": "${TASK_ROLE_ARN}",
    "containerDefinitions": [
        {
            "name": "cloudwatch-mcp-server",
            "image": "${ECR_URI}:latest",
            "essential": true,
            "portMappings": [
                {
                    "containerPort": 8000,
                    "protocol": "tcp"
                }
            ],
            "environment": [
                {
                    "name": "MCP_PORT",
                    "value": "8000"
                },
                {
                    "name": "MCP_HOST",
                    "value": "0.0.0.0"
                },
                {
                    "name": "AWS_DEFAULT_REGION",
                    "value": "${AWS_REGION}"
                }
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "${LOG_GROUP}",
                    "awslogs-region": "${AWS_REGION}",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            "healthCheck": {
                "command": [
                    "CMD-SHELL",
                    "curl -f http://localhost:8000/health || exit 1"
                ],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 60
            }
        }
    ]
}
EOF
)

# Register task definition
echo "📋 Registering task definition..."
NEW_TASK_DEF_ARN=$(aws ecs register-task-definition \
    --region "${AWS_REGION}" \
    --cli-input-json "${TASK_DEF_JSON}" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo "✅ Task definition registered: ${NEW_TASK_DEF_ARN}"

# Check if service exists
echo "🔍 Checking if ECS service exists..."
if aws ecs describe-services --cluster "${ECS_CLUSTER}" --services "${SERVICE_NAME}" --region "${AWS_REGION}" --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo "📋 Service exists, updating..."
    
    # Update existing service
    aws ecs update-service \
        --cluster "${ECS_CLUSTER}" \
        --service "${SERVICE_NAME}" \
        --task-definition "${NEW_TASK_DEF_ARN}" \
        --region "${AWS_REGION}" \
        --force-new-deployment
    
    echo "✅ Service update initiated"
    
else
    echo "📋 Service does not exist, creating new service..."
    
    # Validate network configuration
    if [ -z "${PRIVATE_SUBNETS}" ] || [ -z "${SECURITY_GROUP}" ]; then
        echo "❌ Network configuration missing"
        echo "   PRIVATE_SUBNETS: ${PRIVATE_SUBNETS}"
        echo "   SECURITY_GROUP: ${SECURITY_GROUP}"
        echo "   Set ECS_SUBNETS and ECS_SECURITY_GROUP environment variables"
        exit 1
    fi
    
    # Create service configuration
    SERVICE_CONFIG=$(cat << EOF
{
    "serviceName": "${SERVICE_NAME}",
    "cluster": "${ECS_CLUSTER}",
    "taskDefinition": "${NEW_TASK_DEF_ARN}",
    "desiredCount": 1,
    "launchType": "FARGATE",
    "platformVersion": "LATEST",
    "networkConfiguration": {
        "awsvpcConfiguration": {
            "subnets": ["${PRIVATE_SUBNETS//,/\",\"}"],
            "securityGroups": ["${SECURITY_GROUP}"],
            "assignPublicIp": "DISABLED"
        }
    },
    "healthCheckGracePeriodSeconds": 120,
    "deploymentConfiguration": {
        "maximumPercent": 200,
        "minimumHealthyPercent": 50,
        "deploymentCircuitBreaker": {
            "enable": true,
            "rollback": true
        }
    },
    "enableExecuteCommand": true
}
EOF
)
    
    # Add load balancer configuration if target group is available
    if [ -n "${TARGET_GROUP_ARN}" ]; then
        echo "🔗 Adding load balancer configuration..."
        SERVICE_CONFIG=$(echo "${SERVICE_CONFIG}" | jq --arg tg "${TARGET_GROUP_ARN}" '.loadBalancers = [{"targetGroupArn": $tg, "containerName": "cloudwatch-mcp-server", "containerPort": 8000}]')
    fi
    
    # Create service
    aws ecs create-service \
        --region "${AWS_REGION}" \
        --cli-input-json "${SERVICE_CONFIG}"
    
    echo "✅ Service created successfully"
fi

# Wait for service to stabilize
echo "⏳ Waiting for service to stabilize..."
aws ecs wait services-stable \
    --cluster "${ECS_CLUSTER}" \
    --services "${SERVICE_NAME}" \
    --region "${AWS_REGION}"

echo "✅ Service is stable"

# Get service status
echo "📊 Service Status:"
aws ecs describe-services \
    --cluster "${ECS_CLUSTER}" \
    --services "${SERVICE_NAME}" \
    --region "${AWS_REGION}" \
    --query 'services[0].{ServiceName:serviceName,Status:status,RunningCount:runningCount,DesiredCount:desiredCount,TaskDefinition:taskDefinition}' \
    --output table

echo ""
echo "🎉 MCP Services deployment completed successfully!"
echo ""
echo "📋 Deployment Summary:"
echo "  ECS Cluster: ${ECS_CLUSTER}"
echo "  Service Name: ${SERVICE_NAME}"
echo "  Task Definition: ${NEW_TASK_DEF_ARN}"
echo "  Image: ${ECR_URI}:latest"
echo ""
echo "🔧 Next Steps:"
echo "  1. Verify service health via load balancer"
echo "  2. Test MCP endpoints"
echo "  3. Monitor CloudWatch logs"
echo ""