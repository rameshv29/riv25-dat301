#!/bin/bash
set -euo pipefail

# Workshop Setup Validation Script
# This script validates that all workshop components are properly configured

echo "🔍 Starting workshop setup validation..."

# Configuration
AWS_REGION=${AWS_REGION:-$(aws configure get region || echo "us-east-1")}
PROJECT_NAME=${PROJECT_NAME:-"mcp-servers"}
ENVIRONMENT=${ENVIRONMENT:-"dev"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Validation results
VALIDATION_RESULTS=()
TOTAL_CHECKS=0
PASSED_CHECKS=0

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
    VALIDATION_RESULTS+=("✅ $1")
    ((PASSED_CHECKS++))
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    VALIDATION_RESULTS+=("⚠️  $1")
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
    VALIDATION_RESULTS+=("❌ $1")
}

run_check() {
    local check_name="$1"
    local check_command="$2"
    
    ((TOTAL_CHECKS++))
    log_info "Checking: $check_name"
    
    if eval "$check_command" >/dev/null 2>&1; then
        log_success "$check_name"
        return 0
    else
        log_error "$check_name"
        return 1
    fi
}

# Start validation
echo "📋 Validation Configuration:"
echo "  AWS Region: ${AWS_REGION}"
echo "  Project Name: ${PROJECT_NAME}"
echo "  Environment: ${ENVIRONMENT}"
echo ""

# 1. AWS CLI and Credentials
log_info "=== AWS Configuration ==="
run_check "AWS CLI installed" "aws --version"
run_check "AWS credentials configured" "aws sts get-caller-identity"
run_check "AWS region configured" "test -n '${AWS_REGION}'"

# 2. Docker
log_info "=== Docker Configuration ==="
run_check "Docker installed" "docker --version"
run_check "Docker daemon running" "docker info"

# 3. AgentCore Setup
log_info "=== AgentCore Workshop Setup ==="
run_check "AgentCore repository cloned" "test -d /tmp/amazon-bedrock-agentcore-samples"
run_check "AgentCore Python environment" "test -d /tmp/amazon-bedrock-agentcore-samples/02-use-cases/DB-performance-analyzer/venv"
run_check "AgentCore config directory" "test -d /tmp/amazon-bedrock-agentcore-samples/02-use-cases/DB-performance-analyzer/config"

# 4. VS Code Server
log_info "=== VS Code Server ==="
run_check "VS Code Server container running" "docker ps | grep -q vscode-server"
run_check "VS Code Server port accessible" "curl -f http://localhost:8080 -o /dev/null -s"

# 5. Database Connectivity
log_info "=== Database Configuration ==="
if command -v psql >/dev/null 2>&1; then
    log_success "PostgreSQL client installed"
    ((PASSED_CHECKS++))
    
    # Try to get database connection info from secrets
    if aws secretsmanager list-secrets --region "${AWS_REGION}" --query 'SecretList[?contains(Name, `aurora`) || contains(Name, `database`)].Name' --output text | grep -q .; then
        log_success "Database secrets found in Secrets Manager"
        ((PASSED_CHECKS++))
    else
        log_warning "Database secrets not found in Secrets Manager"
    fi
else
    log_error "PostgreSQL client not installed"
fi
((TOTAL_CHECKS += 2))

# 6. MCP Infrastructure
log_info "=== MCP Infrastructure ==="
ECS_CLUSTER="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
run_check "ECS cluster exists" "aws ecs describe-clusters --clusters '${ECS_CLUSTER}' --region '${AWS_REGION}' --query 'clusters[0].status' --output text | grep -q ACTIVE"

# Check ECR repository
ECR_REPO="${PROJECT_NAME}/${ENVIRONMENT}/cloudwatch-mcp-server"
run_check "ECR repository exists" "aws ecr describe-repositories --repository-names '${ECR_REPO}' --region '${AWS_REGION}'"

# Check if MCP service is running
MCP_SERVICE="${PROJECT_NAME}-${ENVIRONMENT}-cloudwatch-mcp-service"
if aws ecs describe-services --cluster "${ECS_CLUSTER}" --services "${MCP_SERVICE}" --region "${AWS_REGION}" --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    log_success "MCP service is running"
    ((PASSED_CHECKS++))
    
    # Check service health
    RUNNING_COUNT=$(aws ecs describe-services --cluster "${ECS_CLUSTER}" --services "${MCP_SERVICE}" --region "${AWS_REGION}" --query 'services[0].runningCount' --output text 2>/dev/null || echo "0")
    DESIRED_COUNT=$(aws ecs describe-services --cluster "${ECS_CLUSTER}" --services "${MCP_SERVICE}" --region "${AWS_REGION}" --query 'services[0].desiredCount' --output text 2>/dev/null || echo "1")
    
    if [ "${RUNNING_COUNT}" = "${DESIRED_COUNT}" ] && [ "${RUNNING_COUNT}" -gt 0 ]; then
        log_success "MCP service healthy (${RUNNING_COUNT}/${DESIRED_COUNT} tasks running)"
        ((PASSED_CHECKS++))
    else
        log_warning "MCP service not healthy (${RUNNING_COUNT}/${DESIRED_COUNT} tasks running)"
    fi
else
    log_error "MCP service not found or not active"
fi
((TOTAL_CHECKS += 2))

# 7. Load Balancer and Networking
log_info "=== Load Balancer and Networking ==="
ALB_NAME="${PROJECT_NAME}-${ENVIRONMENT}-alb"
if aws elbv2 describe-load-balancers --region "${AWS_REGION}" --query "LoadBalancers[?contains(LoadBalancerName, '${ALB_NAME}')].State.Code" --output text 2>/dev/null | grep -q "active"; then
    log_success "Application Load Balancer is active"
    ((PASSED_CHECKS++))
    
    # Get ALB DNS name for testing
    ALB_DNS=$(aws elbv2 describe-load-balancers --region "${AWS_REGION}" --query "LoadBalancers[?contains(LoadBalancerName, '${ALB_NAME}')].DNSName" --output text 2>/dev/null || echo "")
    if [ -n "${ALB_DNS}" ]; then
        log_info "Testing ALB health endpoint..."
        if curl -f "http://${ALB_DNS}/health" -o /dev/null -s --max-time 10; then
            log_success "ALB health endpoint accessible"
            ((PASSED_CHECKS++))
        else
            log_warning "ALB health endpoint not accessible (may still be starting up)"
        fi
    fi
else
    log_error "Application Load Balancer not found or not active"
fi
((TOTAL_CHECKS += 2))

# 8. CloudWatch Logs
log_info "=== CloudWatch Logs ==="
LOG_GROUP="/ecs/${PROJECT_NAME}/${ENVIRONMENT}/cloudwatch-mcp"
run_check "CloudWatch log group exists" "aws logs describe-log-groups --log-group-name-prefix '${LOG_GROUP}' --region '${AWS_REGION}' --query 'logGroups[0].logGroupName' --output text | grep -q '${LOG_GROUP}'"

# 9. Secrets Manager
log_info "=== Secrets Manager ==="
AGENTCORE_SECRET="${PROJECT_NAME}-agentcore-config"
if aws secretsmanager describe-secret --secret-id "${AGENTCORE_SECRET}" --region "${AWS_REGION}" >/dev/null 2>&1; then
    log_success "AgentCore configuration secret exists"
    ((PASSED_CHECKS++))
else
    log_warning "AgentCore configuration secret not found (may be created during setup)"
fi
((TOTAL_CHECKS++))

# 10. Workshop Files and Permissions
log_info "=== Workshop Files and Permissions ==="
WORKSHOP_USER=${WORKSHOP_USER:-"ec2-user"}
run_check "Workshop user exists" "id '${WORKSHOP_USER}'"
run_check "Workshop home directory accessible" "test -d /home/${WORKSHOP_USER}"

if [ -d "/tmp/amazon-bedrock-agentcore-samples" ]; then
    run_check "Workshop files have correct ownership" "test -O /tmp/amazon-bedrock-agentcore-samples"
else
    log_error "AgentCore samples directory not found"
    ((TOTAL_CHECKS++))
fi

# Summary
echo ""
echo "📊 Validation Summary"
echo "===================="
echo "Total Checks: ${TOTAL_CHECKS}"
echo "Passed: ${PASSED_CHECKS}"
echo "Failed: $((TOTAL_CHECKS - PASSED_CHECKS))"
echo ""

# Calculate success rate
SUCCESS_RATE=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))

if [ ${SUCCESS_RATE} -ge 90 ]; then
    echo -e "${GREEN}🎉 Workshop setup is excellent! (${SUCCESS_RATE}% success rate)${NC}"
    EXIT_CODE=0
elif [ ${SUCCESS_RATE} -ge 75 ]; then
    echo -e "${YELLOW}⚠️  Workshop setup is mostly ready (${SUCCESS_RATE}% success rate)${NC}"
    echo -e "${YELLOW}   Some components may need attention${NC}"
    EXIT_CODE=0
else
    echo -e "${RED}❌ Workshop setup needs attention (${SUCCESS_RATE}% success rate)${NC}"
    echo -e "${RED}   Please review failed checks${NC}"
    EXIT_CODE=1
fi

echo ""
echo "📋 Detailed Results:"
for result in "${VALIDATION_RESULTS[@]}"; do
    echo "  $result"
done

echo ""
echo "🔧 Troubleshooting:"
echo "  - Check CloudWatch logs for service errors"
echo "  - Verify IAM permissions for all services"
echo "  - Ensure all CloudFormation resources are created"
echo "  - Run 'docker logs vscode-server' for VS Code issues"
echo ""

exit ${EXIT_CODE}