#!/bin/bash
# Run ACU stress test to trigger incident

export AWS_REGION=us-west-2
CLUSTER_ARN="arn:aws:rds:us-west-2:653218433608:cluster:dat-ws-v9-idr-acu"
SECRET_ARN="arn:aws:secretsmanager:us-west-2:653218433608:secret:dat-ws-v9-idr-acu-secret-1gF6Sv"
DATABASE="idr_db"

echo "🚀 Starting ACU stress test..."
echo "Cluster: $CLUSTER_ARN"
echo "Duration: 300 seconds (5 minutes)"
echo "Workers: 20"

venv/bin/python stress_test_acu.py \
  -c "$CLUSTER_ARN" \
  -s "$SECRET_ARN" \
  -d "$DATABASE" \
  -t 300 \
  -w 20 \
  -r "$AWS_REGION"

echo "✅ Stress test completed!"
