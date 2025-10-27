#!/usr/bin/env python3
import boto3
import json
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PI-MCP-Server")

def get_pi_client():
    session = boto3.Session(region_name="us-west-2")
    return session.client('pi')

def get_rds_resource_id():
    """Get the correct RDS instance resource ID for Performance Insights"""
    session = boto3.Session(region_name="us-west-2")
    rds_client = session.client('rds')
    
    # Get the instance from the dev-cluster
    response = rds_client.describe_db_instances(DBInstanceIdentifier='dev-cluster-instance-1')
    return response['DBInstances'][0]['DbiResourceId']

@mcp.tool()
def get_performance_insights_metrics(metric_queries: list = None, start_time: str = None, end_time: str = None):
    """Get Performance Insights metrics for RDS instance"""
    try:
        pi_client = get_pi_client()
        resource_id = get_rds_resource_id()
        
        if not start_time:
            start_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        if not end_time:
            end_time = datetime.utcnow().isoformat()
        
        if not metric_queries:
            # Default metrics for lock analysis
            metric_queries = [
                {"Metric": "db.SQL.Innodb_rows_read.avg"},
                {"Metric": "db.wait_event.Lock/transactionid.avg"},
                {"Metric": "db.wait_event.Lock/tuple.avg"}
            ]
        
        response = pi_client.get_resource_metrics(
            ServiceType='RDS',
            Identifier=resource_id,
            MetricQueries=metric_queries,
            StartTime=start_time,
            EndTime=end_time,
            PeriodInSeconds=300
        )
        
        return response
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_top_sql_statements(limit: int = 10):
    """Get top SQL statements from Performance Insights"""
    try:
        pi_client = get_pi_client()
        resource_id = get_rds_resource_id()
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        response = pi_client.describe_dimension_keys(
            ServiceType='RDS',
            Identifier=resource_id,
            Metric='db.load',
            GroupBy={'Group': 'db.sql_tokenized'},
            StartTime=start_time.isoformat(),
            EndTime=end_time.isoformat(),
            MaxResults=limit
        )
        
        return response
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_wait_events(limit: int = 10):
    """Get top wait events from Performance Insights for lock analysis"""
    try:
        pi_client = get_pi_client()
        resource_id = get_rds_resource_id()
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        response = pi_client.describe_dimension_keys(
            ServiceType='RDS',
            Identifier=resource_id,
            Metric='db.load',
            GroupBy={'Group': 'db.wait_event'},
            StartTime=start_time.isoformat(),
            EndTime=end_time.isoformat(),
            MaxResults=limit
        )
        
        return response
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    mcp.run()
