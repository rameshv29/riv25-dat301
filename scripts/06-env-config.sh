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
WORKSHOP_MAIN_STACK=$(find_stack_by_pattern "dat301")
if [ -z "$WORKSHOP_MAIN_STACK" ]; then
    WORKSHOP_MAIN_STACK=$(find_stack_by_pattern "DAT301")
fi
if [ -z "$WORKSHOP_MAIN_STACK" ]; then
    WORKSHOP_MAIN_STACK=$(find_stack_by_pattern "workshop")
fi

echo "🎯 Found main stack: ${WORKSHOP_MAIN_STACK:-'Not found'}"

# Get stack outputs if stack found
if [ -n "$WORKSHOP_MAIN_STACK" ]; then
    echo "📊 Extracting stack outputs..."
    
    DB_ENDPOINT=$(get_stack_output "$WORKSHOP_MAIN_STACK" "DatabaseEndpoint")
    DB_SECRET_ARN=$(get_stack_output "$WORKSHOP_MAIN_STACK" "DatabaseSecretArn")
    COGNITO_USER_POOL_ID=$(get_stack_output "$WORKSHOP_MAIN_STACK" "CognitoUserPoolId")
    COGNITO_CLIENT_ID=$(get_stack_output "$WORKSHOP_MAIN_STACK" "CognitoClientId")
    
    # Try alternative output key names
    if [ -z "$DB_ENDPOINT" ]; then
        DB_ENDPOINT=$(get_stack_output "$WORKSHOP_MAIN_STACK" "RDSEndpoint")
    fi
    if [ -z "$DB_SECRET_ARN" ]; then
        DB_SECRET_ARN=$(get_stack_output "$WORKSHOP_MAIN_STACK" "DatabaseSecret")
    fi
    
    # Construct cluster ARN if we have endpoint
    if [ -n "$DB_ENDPOINT" ]; then
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
        CLUSTER_NAME=$(echo "$DB_ENDPOINT" | cut -d'.' -f1)
        DB_CLUSTER_ARN="arn:aws:rds:$AWS_REGION:$ACCOUNT_ID:cluster:$CLUSTER_NAME"
    fi
    
    echo "✅ Stack outputs discovered:"
    echo "   Database Endpoint: ${DB_ENDPOINT:-'Not found'}"
    echo "   Database Secret: ${DB_SECRET_ARN:-'Not found'}"
    echo "   Cognito User Pool: ${COGNITO_USER_POOL_ID:-'Not found'}"
    echo "   Cognito Client: ${COGNITO_CLIENT_ID:-'Not found'}"
else
    echo "⚠️  No workshop stack found, using defaults"
    DB_ENDPOINT="localhost"
    DB_SECRET_ARN=""
    DB_CLUSTER_ARN=""
    COGNITO_USER_POOL_ID=""
    COGNITO_CLIENT_ID=""
fi

# Create environment configuration
cat > /workshop/.env << EOF
# DAT301 Workshop Environment Variables (Auto-discovered)
AWS_REGION=$AWS_REGION
AWS_DEFAULT_REGION=$AWS_REGION
RDS_CLUSTER_ARN=${DB_CLUSTER_ARN:-}
RDS_SECRET_ARN=${DB_SECRET_ARN:-}
DATABASE_NAME=workshop_db
DATABASE_ENDPOINT=${DB_ENDPOINT:-localhost}
DATABASE_PORT=5432
DATABASE_SECRET_ARN=${DB_SECRET_ARN:-}
HOST=${DB_ENDPOINT:-localhost}
COGNITO_USER_POOL_ID=${COGNITO_USER_POOL_ID:-}
COGNITO_CLIENT_ID=${COGNITO_CLIENT_ID:-}
WORKSHOP_STACK_NAME=${WORKSHOP_MAIN_STACK:-}
EOF

# Set up environment variables for ec2-user
cat >> /home/ec2-user/.bashrc << EOF

# DAT301 Workshop Environment Variables (Auto-discovered)
export AWS_REGION="$AWS_REGION"
export AWS_DEFAULT_REGION="$AWS_REGION"
export RDS_CLUSTER_ARN="${DB_CLUSTER_ARN:-}"
export RDS_SECRET_ARN="${DB_SECRET_ARN:-}"
export DATABASE_NAME=workshop_db
export DATABASE_ENDPOINT="${DB_ENDPOINT:-localhost}"
export DATABASE_PORT=5432
export DATABASE_SECRET_ARN="${DB_SECRET_ARN:-}"
export HOST="${DB_ENDPOINT:-localhost}"
export COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID:-}"
export COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID:-}"
export WORKSHOP_STACK_NAME="${WORKSHOP_MAIN_STACK:-}"

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