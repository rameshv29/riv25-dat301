#!/bin/bash

echo "🚀 Starting Mahavat Agent"

# Check required environment variables for IDR
if [ -z "$AWS_REGION" ]; then
    echo "❌ ERROR: AWS_REGION environment variable is not set"
    exit 1
fi

if [ -z "$IDR_CLUSTER_ARN" ]; then
    echo "❌ ERROR: IDR_CLUSTER_ARN environment variable is not set"
    exit 1
fi

if [ -z "$IDR_SECRET_ARN" ]; then
    echo "❌ ERROR: IDR_SECRET_ARN environment variable is not set"
    exit 1
fi

if [ -z "$IDR_DATABASE_NAME" ]; then
    echo "❌ ERROR: IDR_DATABASE_NAME environment variable is not set"
    exit 1
fi

if [ -z "$DYNAMODB_TABLE" ]; then
    echo "❌ ERROR: DYNAMODB_TABLE environment variable is not set"
    exit 1
fi

# Check required environment variables for PostgreSQL diagnostics
if [ -z "$RDS_CLUSTER_ARN" ]; then
    echo "❌ ERROR: RDS_CLUSTER_ARN environment variable is not set"
    exit 1
fi

if [ -z "$RDS_SECRET_ARN" ]; then
    echo "❌ ERROR: RDS_SECRET_ARN environment variable is not set"
    exit 1
fi

if [ -z "$DATABASE_NAME" ]; then
    echo "❌ ERROR: DATABASE_NAME environment variable is not set"
    exit 1
fi

echo "✅ Environment variables validated"
echo "   Region: $AWS_REGION"
echo "   IDR Database: $IDR_DATABASE_NAME"
echo "   Main Database: $DATABASE_NAME"
echo "   DynamoDB: $DYNAMODB_TABLE"

# Create logs directory
mkdir -p logs

# Activate virtual environment
source /workshop/mahavat_agent/venv/bin/activate

echo "📝 Logs will be written to:"
echo "   Info:  logs/mahavat_v2_info.log"
echo "   Error: logs/mahavat_v2_error.log"
echo ""
echo "💡 To monitor logs in real-time, run:"
echo "   tail -f logs/mahavat_v2_info.log"
echo ""

# Start Mahavat agent with separate logs
streamlit run mahavat_agent_v2.py \
    --server.port 8503 \
    --server.address 0.0.0.0 \
    > >(tee -a logs/mahavat_v2_info.log) \
    2> >(tee -a logs/mahavat_v2_error.log >&2)

echo "✅ Mahavat Agent ready! Access at http://localhost:8503"
