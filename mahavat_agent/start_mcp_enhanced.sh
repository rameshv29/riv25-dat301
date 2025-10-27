#!/bin/bash

echo "🚀 Starting Mahavat Agent"

# Check required environment variables
if [ -z "$AWS_REGION" ]; then
    echo "❌ ERROR: AWS_REGION environment variable is not set"
    exit 1
fi

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
echo "   Database: $DATABASE_NAME"

# Activate virtual environment
source venv_swarm/bin/activate

# Start enhanced MCP agent
streamlit run streamlit_mcp_enhanced.py --server.port 8506 --server.address 0.0.0.0

echo "✅ Mahavat Agent ready! Access at http://localhost:8506"
