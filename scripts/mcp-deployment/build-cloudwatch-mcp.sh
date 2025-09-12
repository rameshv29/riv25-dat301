#!/bin/bash
set -euo pipefail

# CloudWatch MCP Server Build and Deploy Script
# This script builds the CloudWatch MCP server Docker image and pushes it to ECR

echo "🚀 Starting CloudWatch MCP Server build and deployment..."

# Configuration
PROJECT_NAME=${PROJECT_NAME:-"mcp-servers"}
ENVIRONMENT=${ENVIRONMENT:-"dev"}
AWS_REGION=${AWS_REGION:-$(aws configure get region || echo "us-east-1")}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}

# ECR Repository name (should match CloudFormation template)
ECR_REPO_NAME="${PROJECT_NAME}/${ENVIRONMENT}/cloudwatch-mcp-server"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

# Build configuration
DOCKER_TAG="latest"
BUILD_TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo "📋 Build Configuration:"
echo "  Project: ${PROJECT_NAME}"
echo "  Environment: ${ENVIRONMENT}"
echo "  AWS Region: ${AWS_REGION}"
echo "  AWS Account: ${AWS_ACCOUNT_ID}"
echo "  ECR Repository: ${ECR_REPO_NAME}"
echo "  ECR URI: ${ECR_URI}"
echo "  Build Timestamp: ${BUILD_TIMESTAMP}"

# Change to the CloudWatch MCP directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MCP_DIR="${REPO_ROOT}/docker/mcp-servers/cloudwatch-mcp"

if [ ! -d "${MCP_DIR}" ]; then
    echo "❌ CloudWatch MCP directory not found: ${MCP_DIR}"
    exit 1
fi

cd "${MCP_DIR}"
echo "📁 Working directory: $(pwd)"

# Verify Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    echo "❌ Dockerfile not found in ${MCP_DIR}"
    exit 1
fi

# Get ECR login token
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Check if ECR repository exists, create if it doesn't
echo "🏗️ Checking ECR repository..."
if ! aws ecr describe-repositories --repository-names "${ECR_REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
    echo "📦 Creating ECR repository: ${ECR_REPO_NAME}"
    aws ecr create-repository \
        --repository-name "${ECR_REPO_NAME}" \
        --region "${AWS_REGION}" \
        --image-scanning-configuration scanOnPush=true \
        --tags Key=Project,Value="${PROJECT_NAME}" Key=Environment,Value="${ENVIRONMENT}" Key=Component,Value=CloudWatchMCP
else
    echo "✅ ECR repository exists: ${ECR_REPO_NAME}"
fi

# Build Docker image
echo "🔨 Building Docker image..."
docker build \
    --tag "cloudwatch-mcp-server:${DOCKER_TAG}" \
    --tag "cloudwatch-mcp-server:${BUILD_TIMESTAMP}" \
    --tag "${ECR_URI}:${DOCKER_TAG}" \
    --tag "${ECR_URI}:${BUILD_TIMESTAMP}" \
    --build-arg BUILD_TIMESTAMP="${BUILD_TIMESTAMP}" \
    .

echo "✅ Docker image built successfully"

# Push to ECR
echo "📤 Pushing image to ECR..."
docker push "${ECR_URI}:${DOCKER_TAG}"
docker push "${ECR_URI}:${BUILD_TIMESTAMP}"

echo "✅ Image pushed to ECR successfully"

# Verify the image
echo "🔍 Verifying image in ECR..."
aws ecr describe-images \
    --repository-name "${ECR_REPO_NAME}" \
    --region "${AWS_REGION}" \
    --image-ids imageTag="${DOCKER_TAG}" \
    --query 'imageDetails[0].{ImageDigest:imageDigest,ImageSizeInBytes:imageSizeInBytes,ImagePushedAt:imagePushedAt}' \
    --output table

# Test the image locally (optional)
if [ "${TEST_LOCAL:-false}" = "true" ]; then
    echo "🧪 Testing image locally..."
    
    # Stop any existing container
    docker stop cloudwatch-mcp-test 2>/dev/null || true
    docker rm cloudwatch-mcp-test 2>/dev/null || true
    
    # Run test container
    docker run -d \
        --name cloudwatch-mcp-test \
        -p 8001:8000 \
        -e AWS_DEFAULT_REGION="${AWS_REGION}" \
        "${ECR_URI}:${DOCKER_TAG}"
    
    # Wait for container to start
    sleep 10
    
    # Test health endpoint
    if curl -f http://localhost:8001/health >/dev/null 2>&1; then
        echo "✅ Local test passed"
    else
        echo "❌ Local test failed"
        docker logs cloudwatch-mcp-test
    fi
    
    # Cleanup test container
    docker stop cloudwatch-mcp-test
    docker rm cloudwatch-mcp-test
fi

# Output deployment information
echo ""
echo "🎉 CloudWatch MCP Server build completed successfully!"
echo ""
echo "📋 Deployment Information:"
echo "  ECR Repository: ${ECR_REPO_NAME}"
echo "  Image URI: ${ECR_URI}:${DOCKER_TAG}"
echo "  Build Timestamp: ${BUILD_TIMESTAMP}"
echo ""
echo "🔧 Next Steps:"
echo "  1. Update ECS task definition with new image URI"
echo "  2. Deploy or update ECS service"
echo "  3. Verify service health"
echo ""

# Save deployment info for other scripts
cat > "${REPO_ROOT}/deployment-info.json" << EOF
{
    "cloudwatch_mcp": {
        "ecr_repository": "${ECR_REPO_NAME}",
        "image_uri": "${ECR_URI}:${DOCKER_TAG}",
        "build_timestamp": "${BUILD_TIMESTAMP}",
        "aws_region": "${AWS_REGION}",
        "aws_account_id": "${AWS_ACCOUNT_ID}"
    }
}
EOF

echo "💾 Deployment information saved to deployment-info.json"