#!/bin/bash
set -e

echo "🚀 DAT301 Workshop - Complete Setup"
echo "===================================="

STACK_NAME="dat301-ws-test8-stack"
REGION="us-west-2"

# Get all secrets and values
echo "📥 Fetching stack outputs..."

MAIN_SECRET_ARN="arn:aws:secretsmanager:us-west-2:653218433608:secret:dat301-ws-test8-db-master-credentials-dat301-ws-test8-stack-DatabaseStack-PG8696KCHEDB-eYpChm"
ACU_SECRET_ARN="arn:aws:secretsmanager:us-west-2:653218433608:secret:dat301-ws-test8-idr-acu-secret-OIJEaD"
IOPS_SECRET_ARN="arn:aws:secretsmanager:us-west-2:653218433608:secret:dat301-ws-test8-idr-instance-secret-z957g7"

# Get Main DB credentials
MAIN_SECRET=$(aws secretsmanager get-secret-value --secret-id "$MAIN_SECRET_ARN" --region $REGION --query SecretString --output text)
MAIN_HOST=$(echo $MAIN_SECRET | jq -r .host)
MAIN_PORT=$(echo $MAIN_SECRET | jq -r .port)
MAIN_USER=$(echo $MAIN_SECRET | jq -r .username)
MAIN_PASS=$(echo $MAIN_SECRET | jq -r .password)
MAIN_DB=$(echo $MAIN_SECRET | jq -r .dbname)

# Get ACU DB credentials
ACU_SECRET=$(aws secretsmanager get-secret-value --secret-id "$ACU_SECRET_ARN" --region $REGION --query SecretString --output text)
ACU_HOST=$(echo $ACU_SECRET | jq -r .host)
ACU_PORT=$(echo $ACU_SECRET | jq -r .port)
ACU_USER=$(echo $ACU_SECRET | jq -r .username)
ACU_PASS=$(echo $ACU_SECRET | jq -r .password)
ACU_DB=$(echo $ACU_SECRET | jq -r .dbname)

# Get IOPS DB credentials
IOPS_SECRET=$(aws secretsmanager get-secret-value --secret-id "$IOPS_SECRET_ARN" --region $REGION --query SecretString --output text)
IOPS_HOST=$(echo $IOPS_SECRET | jq -r .host)
IOPS_PORT=$(echo $IOPS_SECRET | jq -r .port)
IOPS_USER=$(echo $IOPS_SECRET | jq -r .username)
IOPS_PASS=$(echo $IOPS_SECRET | jq -r .password)
IOPS_DB=$(echo $IOPS_SECRET | jq -r .dbname)

# Other values
MAIN_KB_ID="TRJGLMJ5AG"
IDR_KB_ID="MIDMLYVXIB"
DYNAMODB_TABLE="dat301-ws-test8-incidents"
IDR_CLUSTER_ARN="arn:aws:rds:us-west-2:653218433608:cluster:dat301-ws-test8-idr-acu"

echo "✅ Stack outputs fetched"

# 1. Create psql connection functions in bashrc
echo "📝 Creating psql connection functions..."
cat >> /home/ec2-user/.bashrc << 'BASHRC_EOF'

# PostgreSQL Connection Functions
function psql_main() {
  PGHOST='dat301-ws-test8-cluster.cluster-cdkfojygv0zu.us-west-2.rds.amazonaws.com'
  PGPORT='5432'
  PGUSER='postgres'
  PGPASSWORD='MAIN_PASS_PLACEHOLDER'
  PGDATABASE='dms_sample'
  psql "$@"
}

function psql_idr_acu() {
  PGHOST='dat301-ws-test8-idr-acu.cluster-cdkfojygv0zu.us-west-2.rds.amazonaws.com'
  PGPORT='5432'
  PGUSER='postgres'
  PGPASSWORD='ACU_PASS_PLACEHOLDER'
  PGDATABASE='idr_db'
  psql "$@"
}

function psql_idr_iops() {
  PGHOST='dat301-ws-test8-idr-instance.cdkfojygv0zu.us-west-2.rds.amazonaws.com'
  PGPORT='5432'
  PGUSER='postgres'
  PGPASSWORD='IOPS_PASS_PLACEHOLDER'
  PGDATABASE='postgres'
  psql "$@"
}
BASHRC_EOF

# Replace placeholders with actual passwords
sed -i "s/MAIN_PASS_PLACEHOLDER/$MAIN_PASS/g" /home/ec2-user/.bashrc
sed -i "s/ACU_PASS_PLACEHOLDER/$ACU_PASS/g" /home/ec2-user/.bashrc
sed -i "s/IOPS_PASS_PLACEHOLDER/$IOPS_PASS/g" /home/ec2-user/.bashrc

echo "✅ psql functions created"

# 2-9. Create comprehensive profile.d with all environment variables
echo "🔧 Creating workshop environment variables..."
cat > /etc/profile.d/workshop-env.sh << PROFILE_EOF
#!/bin/bash
# DAT301 Workshop Environment Variables

# AWS Configuration
export AWS_REGION=$REGION
export AWS_DEFAULT_REGION=$REGION
export WORKSHOP_STACK_NAME=$STACK_NAME

# Main Database (Production)
export RDS_CLUSTER_ARN=arn:aws:rds:$REGION:653218433608:cluster:dat301-ws-test8-cluster
export RDS_SECRET_ARN=$MAIN_SECRET_ARN
export DATABASE_NAME=$MAIN_DB
export DB_SECRET_ARN=$MAIN_SECRET_ARN
export DB_ENDPOINT=$MAIN_HOST
export DB_PORT=$MAIN_PORT
export DB_USER=$MAIN_USER
export DB_PASS=$MAIN_PASS
export DB_NAME=$MAIN_DB
export MAIN_SECRET_ARN=$MAIN_SECRET_ARN

# PostgreSQL defaults (main database)
export PGHOST=$MAIN_HOST
export PGPORT=$MAIN_PORT
export PGUSER=$MAIN_USER
export PGPASSWORD=$MAIN_PASS
export PGDATABASE=$MAIN_DB

# Legacy aliases
export DATABASE_ENDPOINT=$MAIN_HOST
export DATABASE_PORT=$MAIN_PORT
export DATABASE_SECRET_ARN=$MAIN_SECRET_ARN
export HOST=$MAIN_HOST

# IDR ACU Cluster
export IDR_CLUSTER_ARN=$IDR_CLUSTER_ARN
export IDR_SECRET_ARN=$ACU_SECRET_ARN
export IDR_DATABASE_NAME=$ACU_DB
export ACU_SECRET_ARN=$ACU_SECRET_ARN
export IDR_CLUSTER_ENDPOINT=$ACU_HOST

# IDR IOPS Instance
export IOPS_SECRET_ARN=$IOPS_SECRET_ARN
export IDR_IOPS_ENDPOINT=$IOPS_HOST

# Knowledge Bases
export MAIN_KB_ID=$MAIN_KB_ID
export IDR_KB_ID=$IDR_KB_ID

# DynamoDB
export DYNAMODB_TABLE=$DYNAMODB_TABLE
export INCIDENT_TABLE=$DYNAMODB_TABLE

# Cognito
export COGNITO_USER_POOL_ID=us-west-2_TZf8jmtab
export COGNITO_CLIENT_ID=5vvvfj2hufljsoc85nes28gcf8

# Load testing aliases
alias iops-test='/workshop/load-test/run_stress_test.sh -s \$IOPS_SECRET_ARN -w IO'
alias acu-test='/workshop/load-test/run_stress_test.sh -s \$ACU_SECRET_ARN -w CPU'
alias main-test='/workshop/load-test/run_stress_test.sh -s \$MAIN_SECRET_ARN -w CPU'

# Auto-activate virtual environment
if [ -f /workshop/mahavat_agent/venv/bin/activate ]; then
    source /workshop/mahavat_agent/venv/bin/activate
fi

# Workshop helper
alias workshop-env='env | grep -E "(AWS_|RDS_|DATABASE_|IDR_|PGHOST|PGPORT|PGUSER|PGDATABASE|KB_ID|DYNAMODB)" | sort'

echo "DAT301 Workshop environment loaded! Use 'workshop-env' to see all variables."
PROFILE_EOF

chmod +x /etc/profile.d/workshop-env.sh
echo "✅ Environment variables configured"

# 10. Setup mahavat_agent venv
echo "🐍 Setting up Python virtual environment..."
cd /workshop/mahavat_agent

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate and install requirements
source venv/bin/activate
pip3 install -q -r requirements.txt
deactivate

echo "✅ Python dependencies installed"

# 14. Setup pgbench on IDR IOPS instance
echo "🔧 Setting up pgbench on IDR IOPS instance..."
export PGPASSWORD=$IOPS_PASS
pgbench -i -s 200 -h $IOPS_HOST -p $IOPS_PORT -U $IOPS_USER -d $IOPS_DB 2>&1 || echo "⚠️  pgbench setup failed (may already exist)"
unset PGPASSWORD

echo "✅ pgbench setup completed"

# Set ownership
chown -R ec2-user:ec2-user /workshop
chown ec2-user:ec2-user /home/ec2-user/.bashrc

echo ""
echo "🎉 Workshop setup completed successfully!"
echo ""
echo "Available commands:"
echo "  - psql_main       : Connect to main database"
echo "  - psql_idr_acu    : Connect to IDR ACU cluster"
echo "  - psql_idr_iops   : Connect to IDR IOPS instance"
echo "  - iops-test       : Run IOPS stress test"
echo "  - acu-test        : Run ACU stress test"
echo "  - workshop-env    : Show all environment variables"
echo ""
echo "To start IDR agent:"
echo "  cd /workshop/mahavat_agent && ./start_idr.sh"
echo ""
