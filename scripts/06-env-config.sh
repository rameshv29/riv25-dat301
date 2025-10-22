#!/bin/bash
echo "🔧 DAT301 Workshop - Environment Configuration with CloudFormation Discovery"

# Set default region
AWS_REGION="${AWS_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="$AWS_REGION"

echo "🔍 Discovering CloudFormation stacks in region: $AWS_REGION"

# Function to get stack output
get_stack_output() {
    local stack_name="$1"
    local output_key="$2"
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$AWS_REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue" \
        --output text 2>/dev/null || echo ""
}

# Function to find stacks by pattern
find_stack_by_pattern() {
    local pattern="$1"
    aws cloudformation list-stacks \
        --region "$AWS_REGION" \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
        --query "StackSummaries[?contains(StackName, '$pattern')].StackName" \
        --output text 2>/dev/null | head -1
}

# Discover workshop stacks
echo "📋 Searching for workshop stacks..."
DATABASE_STACK=$(find_stack_by_pattern "DatabaseStack")
COGNITO_STACK=$(find_stack_by_pattern "CognitoStack")

echo "🎯 Found Database stack: ${DATABASE_STACK:-'Not found'}"
echo "🎯 Found Cognito stack: ${COGNITO_STACK:-'Not found'}"

# Get database outputs
if [ -n "$DATABASE_STACK" ]; then
    echo "📊 Extracting database outputs..."
    DB_ENDPOINT=$(get_stack_output "$DATABASE_STACK" "DBEndpoint")
    DB_SECRET_ARN=$(get_stack_output "$DATABASE_STACK" "DBSecretArn")
    DB_CLUSTER_ARN=$(get_stack_output "$DATABASE_STACK" "DBClusterArn")
    DB_CLUSTER_ID=$(get_stack_output "$DATABASE_STACK" "DBClusterIdentifier")
    DB_PORT=$(get_stack_output "$DATABASE_STACK" "DBPort")
    ENGINE_VERSION=$(get_stack_output "$DATABASE_STACK" "EngineVersion")
else
    echo "⚠️  Database stack not found"
    DB_ENDPOINT="localhost"
    DB_SECRET_ARN=""
    DB_CLUSTER_ARN=""
    DB_CLUSTER_ID=""
    DB_PORT="5432"
    ENGINE_VERSION=""
fi

# Get Cognito outputs
if [ -n "$COGNITO_STACK" ]; then
    echo "📊 Extracting Cognito outputs..."
    COGNITO_USER_POOL_ID=$(get_stack_output "$COGNITO_STACK" "UserPoolId")
    COGNITO_CLIENT_ID=$(get_stack_output "$COGNITO_STACK" "ClientId")
    COGNITO_IDENTITY_POOL_ID=$(get_stack_output "$COGNITO_STACK" "IdentityPoolId")
    ADMIN_USERNAME=$(get_stack_output "$COGNITO_STACK" "AdminUsername")
    READONLY_USERNAME=$(get_stack_output "$COGNITO_STACK" "ReadonlyUsername")
    DEFAULT_PASSWORD=$(get_stack_output "$COGNITO_STACK" "DefaultPassword")
else
    echo "⚠️  Cognito stack not found"
    COGNITO_USER_POOL_ID=""
    COGNITO_CLIENT_ID=""
    COGNITO_IDENTITY_POOL_ID=""
    ADMIN_USERNAME="admin"
    READONLY_USERNAME="readonly"
    DEFAULT_PASSWORD="TempPass123!"
fi

echo "✅ Stack outputs discovered:"
echo "   Database Endpoint: ${DB_ENDPOINT:-'Not found'}"
echo "   Database Secret: ${DB_SECRET_ARN:-'Not found'}"
echo "   Database Cluster: ${DB_CLUSTER_ID:-'Not found'}"
echo "   Cognito User Pool: ${COGNITO_USER_POOL_ID:-'Not found'}"
echo "   Cognito Client: ${COGNITO_CLIENT_ID:-'Not found'}"

# Create environment configuration
cat > /workshop/.env << EOF
# DAT301 Workshop Environment Variables (Auto-discovered from CloudFormation)
AWS_REGION=$AWS_REGION
AWS_DEFAULT_REGION=$AWS_REGION

# Database Configuration
DATABASE_ENDPOINT=${DB_ENDPOINT:-localhost}
DATABASE_PORT=${DB_PORT:-5432}
DATABASE_NAME=workshop_db
DB_CLUSTER_IDENTIFIER=${DB_CLUSTER_ID:-}
DB_CLUSTER_ARN=${DB_CLUSTER_ARN:-}
DB_SECRET_ARN=${DB_SECRET_ARN:-}
ENGINE_VERSION=${ENGINE_VERSION:-}

# Legacy aliases for compatibility
RDS_CLUSTER_ARN=${DB_CLUSTER_ARN:-}
RDS_SECRET_ARN=${DB_SECRET_ARN:-}
DATABASE_SECRET_ARN=${DB_SECRET_ARN:-}
HOST=${DB_ENDPOINT:-localhost}

# Cognito Configuration
COGNITO_USER_POOL_ID=${COGNITO_USER_POOL_ID:-}
COGNITO_CLIENT_ID=${COGNITO_CLIENT_ID:-}
COGNITO_IDENTITY_POOL_ID=${COGNITO_IDENTITY_POOL_ID:-}
ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
READONLY_USERNAME=${READONLY_USERNAME:-readonly}
DEFAULT_PASSWORD=${DEFAULT_PASSWORD:-TempPass123!}

# Stack Information
DATABASE_STACK_NAME=${DATABASE_STACK:-}
COGNITO_STACK_NAME=${COGNITO_STACK:-}
EOF

# Set up environment variables for ec2-user
cat >> /home/ec2-user/.bashrc << EOF

# DAT301 Workshop Environment Variables (Auto-discovered)
export AWS_REGION="$AWS_REGION"
export AWS_DEFAULT_REGION="$AWS_REGION"

# Database Configuration
export DATABASE_ENDPOINT="${DB_ENDPOINT:-localhost}"
export DATABASE_PORT="${DB_PORT:-5432}"
export DATABASE_NAME=workshop_db
export DB_CLUSTER_IDENTIFIER="${DB_CLUSTER_ID:-}"
export DB_CLUSTER_ARN="${DB_CLUSTER_ARN:-}"
export DB_SECRET_ARN="${DB_SECRET_ARN:-}"

# Legacy aliases
export RDS_CLUSTER_ARN="${DB_CLUSTER_ARN:-}"
export RDS_SECRET_ARN="${DB_SECRET_ARN:-}"
export DATABASE_SECRET_ARN="${DB_SECRET_ARN:-}"
export HOST="${DB_ENDPOINT:-localhost}"

# Cognito Configuration
export COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID:-}"
export COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID:-}"
export COGNITO_IDENTITY_POOL_ID="${COGNITO_IDENTITY_POOL_ID:-}"
export ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
export READONLY_USERNAME="${READONLY_USERNAME:-readonly}"

# Workshop shortcuts
alias workshop-env='env | grep -E "(AWS_|RDS_|DATABASE_|HOST|COGNITO_|WORKSHOP_)" | sort'
alias workshop-info='echo "DAT301 Workshop Environment - Use workshop-env to see all variables"'
alias workshop-reload='source /workshop/.env && echo "Environment reloaded from /workshop/.env"'

# Auto-load workshop directory and environment
cd /workshop 2>/dev/null || true
if [ -f /workshop/.env ]; then
    set -a; source /workshop/.env; set +a
fi

echo "DAT301 Workshop environment loaded! Use 'workshop-env' to see all variables."
EOF

# Set ownership
chown ec2-user:ec2-user /workshop/.env

echo "✅ Environment configuration completed with CloudFormation discovery"
echo "📁 Environment file created: /workshop/.env"
echo "🔄 Run 'source ~/.bashrc' or start a new shell to load environment"