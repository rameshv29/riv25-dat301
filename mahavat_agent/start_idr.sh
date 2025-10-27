#!/bin/bash

echo "🚀 Starting IDR Agent"

# Check required environment variables
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

echo "✅ Environment variables validated"
echo "   Region: $AWS_REGION"
echo "   Database: $IDR_DATABASE_NAME"
echo "   DynamoDB: $DYNAMODB_TABLE"

# Activate virtual environment
source /workshop/mahavat_agent/venv/bin/activate

# Start IDR agent
streamlit run streamlit_idr_ui.py --server.port 8501 --server.address 0.0.0.0

echo "✅ IDR Agent ready! Access at http://localhost:8501"
