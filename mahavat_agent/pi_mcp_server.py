#!/usr/bin/env python3
import boto3
import json
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PI-MCP-Server")

def get_pi_client():
    session = boto3.Session(region_name="us-west-2")
    return session.client('pi')

def get_rds_resource_id(cluster_identifier: str):
    """Get the correct RDS instance resource ID for Performance Insights"""
    session = boto3.Session(region_name="us-west-2")
    rds_client = session.client('rds')
    
    # Get the instance
    response = rds_client.describe_db_instances(DBInstanceIdentifier=cluster_identifier)
    return response['DBInstances'][0]['DbiResourceId']

@mcp.tool()
def get_performance_insights_metrics(cluster_identifier: str, metric_queries: list = None, start_time: str = None, end_time: str = None):
    """Get Performance Insights metrics for RDS instance
    
    Args:
        cluster_identifier: RDS instance identifier (REQUIRED)
        metric_queries: List of metric queries
        start_time: Start time in ISO format
        end_time: End time in ISO format
    """
    try:
        if not cluster_identifier:
            return {"error": "cluster_identifier is required. Please provide the RDS instance identifier."}
        
        pi_client = get_pi_client()
        resource_id = get_rds_resource_id(cluster_identifier)
        
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
def get_top_sql_statements(cluster_identifier: str, limit: int = 10):
    """Get top SQL statements from Performance Insights
    
    Args:
        cluster_identifier: RDS instance identifier (REQUIRED)
        limit: Maximum number of results to return
    """
    try:
        if not cluster_identifier:
            return {"error": "cluster_identifier is required. Please provide the RDS instance identifier."}
        
        pi_client = get_pi_client()
        resource_id = get_rds_resource_id(cluster_identifier)
        
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
def get_wait_events(cluster_identifier: str, limit: int = 10):
    """Get top wait events from Performance Insights for lock analysis
    
    Args:
        cluster_identifier: RDS instance identifier (REQUIRED)
        limit: Maximum number of results to return
    """
    try:
        if not cluster_identifier:
            return {"error": "cluster_identifier is required. Please provide the RDS instance identifier."}
        
        pi_client = get_pi_client()
        resource_id = get_rds_resource_id(cluster_identifier)
        
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
