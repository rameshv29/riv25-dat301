#!/bin/bash
echo "🔧 DAT301 Workshop - Environment Configuration"

# Set up environment variables for ec2-user
cat >> /home/ec2-user/.bashrc << EOF

# DAT301 Workshop Environment Variables
export AWS_REGION="${AWS_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="${AWS_REGION:-us-west-2}"
export RDS_CLUSTER_ARN="${RDS_CLUSTER_ARN:-}"
export RDS_SECRET_ARN="${RDS_SECRET_ARN:-}"
export DATABASE_NAME=workshop_db
export DATABASE_ENDPOINT="${DATABASE_ENDPOINT:-localhost}"
export DATABASE_PORT=5432
export DATABASE_SECRET_ARN="${DATABASE_SECRET_ARN:-}"
export HOST="${DATABASE_ENDPOINT:-localhost}"
export COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID:-}"
export COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID:-}"

# Workshop shortcuts
alias workshop-env='env | grep -E "(AWS_|RDS_|DATABASE_|HOST|COGNITO_)" | sort'
alias workshop-info='echo "DAT301 Workshop Environment - Use workshop-env to see all variables"'

# Auto-load workshop directory
cd /workshop 2>/dev/null || true

echo "DAT301 Workshop environment loaded! Use 'workshop-env' to see all variables."
EOF

# Set up for root user
cat >> /root/.bashrc << EOF

# DAT301 Workshop Environment Variables
export AWS_REGION="${AWS_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="${AWS_REGION:-us-west-2}"
export RDS_CLUSTER_ARN="${RDS_CLUSTER_ARN:-}"
export RDS_SECRET_ARN="${RDS_SECRET_ARN:-}"
export DATABASE_NAME=workshop_db
export DATABASE_ENDPOINT="${DATABASE_ENDPOINT:-localhost}"
export DATABASE_PORT=5432
export DATABASE_SECRET_ARN="${DATABASE_SECRET_ARN:-}"
export HOST="${DATABASE_ENDPOINT:-localhost}"
export COGNITO_USER_POOL_ID="${COGNITO_USER_POOL_ID:-}"
export COGNITO_CLIENT_ID="${COGNITO_CLIENT_ID:-}"
EOF

# Create system-wide environment file
cat > /etc/environment << EOF
AWS_REGION=${AWS_REGION:-us-west-2}
AWS_DEFAULT_REGION=${AWS_REGION:-us-west-2}
RDS_CLUSTER_ARN=${RDS_CLUSTER_ARN:-}
RDS_SECRET_ARN=${RDS_SECRET_ARN:-}
DATABASE_NAME=workshop_db
DATABASE_ENDPOINT=${DATABASE_ENDPOINT:-localhost}
DATABASE_PORT=5432
DATABASE_SECRET_ARN=${DATABASE_SECRET_ARN:-}
HOST=${DATABASE_ENDPOINT:-localhost}
COGNITO_USER_POOL_ID=${COGNITO_USER_POOL_ID:-}
COGNITO_CLIENT_ID=${COGNITO_CLIENT_ID:-}
EOF

echo "✅ Environment configuration completed"