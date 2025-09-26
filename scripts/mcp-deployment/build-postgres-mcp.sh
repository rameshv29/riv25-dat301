#!/bin/bash
set -euo pipefail

# PostgreSQL MCP Server Build Script
# This script builds the PostgreSQL MCP server Docker image and pushes it to ECR

echo "🚀 Starting PostgreSQL MCP Server build..."

# Configuration
PROJECT_NAME=${PROJECT_NAME:-"mcp-servers"}
ENVIRONMENT=${ENVIRONMENT:-"dev"}
AWS_REGION=${AWS_REGION:-$(aws configure get region || echo "us-east-1")}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}

# ECR Configuration
ECR_REPO_NAME="${PROJECT_NAME}/${ENVIRONMENT}/postgres-mcp-server"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "📋 Build Configuration:"
echo "  Project: ${PROJECT_NAME}"
echo "  Environment: ${ENVIRONMENT}"
echo "  AWS Region: ${AWS_REGION}"
echo "  ECR URI: ${ECR_URI}"

# Get script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
POSTGRES_MCP_DIR="${REPO_ROOT}/mcpservers/postgres-mcp-server"

# Verify PostgreSQL MCP server directory exists
if [ ! -d "${POSTGRES_MCP_DIR}" ]; then
    echo "❌ PostgreSQL MCP server directory not found: ${POSTGRES_MCP_DIR}"
    exit 1
fi

echo "✅ PostgreSQL MCP server directory found: ${POSTGRES_MCP_DIR}"

# Login to ECR
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Create ECR repository if it doesn't exist
echo "📦 Ensuring ECR repository exists..."
if ! aws ecr describe-repositories --repository-names "${ECR_REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
    echo "🆕 Creating ECR repository: ${ECR_REPO_NAME}"
    aws ecr create-repository \
        --repository-name "${ECR_REPO_NAME}" \
        --region "${AWS_REGION}" \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256
else
    echo "✅ ECR repository already exists: ${ECR_REPO_NAME}"
fi

# Detect architecture and set platform
HOST_ARCH=$(uname -m)
if [[ "${HOST_ARCH}" == "aarch64" ]] || [[ "${HOST_ARCH}" == "arm64" ]]; then
    DOCKER_PLATFORM="linux/arm64"
    echo "📋 Building for ARM64 platform (native)"
else
    DOCKER_PLATFORM="linux/amd64"
    echo "📋 Building for AMD64 platform (native)"
fi

# Build Docker image
echo "🔨 Building PostgreSQL MCP server Docker image..."
cd "${POSTGRES_MCP_DIR}"

# Build the image for the native platform
docker build \
    --platform "${DOCKER_PLATFORM}" \
    --tag "${ECR_URI}:latest" \
    --tag "${ECR_URI}:$(date +%Y%m%d-%H%M%S)" \
    .

echo "✅ Docker image built successfully"

# Push to ECR
echo "📤 Pushing image to ECR..."
docker push "${ECR_URI}:latest"

# Also push the timestamped version
TIMESTAMP_TAG="${ECR_URI}:$(date +%Y%m%d-%H%M%S)"
docker push "${TIMESTAMP_TAG}"

echo "✅ Image pushed to ECR successfully"

# Verify the image
echo "🔍 Verifying pushed image..."
aws ecr describe-images \
    --repository-name "${ECR_REPO_NAME}" \
    --region "${AWS_REGION}" \
    --query 'imageDetails[0].{Digest:imageDigest,Tags:imageTags,Size:imageSizeInBytes,Pushed:imagePushedAt}' \
    --output table

echo ""
echo "🎉 PostgreSQL MCP Server build completed successfully!"
echo ""
echo "📋 Build Summary:"
echo "  ECR Repository: ${ECR_REPO_NAME}"
echo "  Image URI: ${ECR_URI}:latest"
echo "  Platform: ${DOCKER_PLATFORM}"
echo ""
echo "🔧 Next Steps:"
echo "  1. Deploy the service using deploy-services.sh"
echo "  2. Test the endpoints"
echo "  3. Monitor CloudWatch logs"
echo ""