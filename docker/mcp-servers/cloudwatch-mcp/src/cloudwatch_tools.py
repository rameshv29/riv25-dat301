"""
CloudWatch Tools for MCP Server
Provides CloudWatch metrics and logs functionality
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

import aioboto3
import structlog
from botocore.exceptions import ClientError, NoCredentialsError

logger = structlog.get_logger()


class CloudWatchTools:
    """CloudWatch tools for metrics and logs access"""
    
    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.session = None
        self.cloudwatch_client = None
        self.logs_client = None
        
    async def initialize(self):
        """Initialize AWS clients"""
        try:
            self.session = aioboto3.Session()
            
            # Create CloudWatch client
            self.cloudwatch_client = self.session.client(
                'cloudwatch',
                region_name=self.region
            )
            
            # Create CloudWatch Logs client
            self.logs_client = self.session.client(
                'logs',
                region_name=self.region
            )
            
            logger.info("CloudWatch tools initialized", region=self.region)
            
        except Exception as e:
            logger.error("Failed to initialize CloudWatch tools", error=str(e))
            raise
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.cloudwatch_client:
                await self.cloudwatch_client.close()
            if self.logs_client:
                await self.logs_client.close()
            logger.info("CloudWatch tools cleaned up")
        except Exception as e:
            logger.error("Error during cleanup", error=str(e))
    
    async def health_check(self) -> bool:
        """Check CloudWatch service health"""
        try:
            async with self.cloudwatch_client as cw:
                # Simple API call to test connectivity
                await cw.list_metrics(MaxRecords=1)
            return True
        except Exception as e:
            logger.error("CloudWatch health check failed", error=str(e))
            return False
    
    async def get_metrics(
        self,
        namespace: str,
        metric_name: str,
        dimensions: Optional[Dict[str, str]] = None,
        start_time: str,
        end_time: str,
        period: int = 300,
        statistic: str = "Average"
    ) -> List[Dict[str, Any]]:
        """Get CloudWatch metrics"""
        try:
            # Parse time strings
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            # Build dimensions list
            dimensions_list = []
            if dimensions:
                dimensions_list = [
                    {"Name": name, "Value": value}
                    for name, value in dimensions.items()
                ]
            
            async with self.cloudwatch_client as cw:
                response = await cw.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    Dimensions=dimensions_list,
                    StartTime=start_dt,
                    EndTime=end_dt,
                    Period=period,
                    Statistics=[statistic]
                )
            
            # Format response
            datapoints = []
            for point in response.get('Datapoints', []):
                datapoints.append({
                    'timestamp': point['Timestamp'].isoformat(),
                    'value': point.get(statistic, 0),
                    'unit': point.get('Unit', 'None')
                })
            
            # Sort by timestamp
            datapoints.sort(key=lambda x: x['timestamp'])
            
            logger.info(
                "Retrieved metrics",
                namespace=namespace,
                metric_name=metric_name,
                count=len(datapoints)
            )
            
            return datapoints
            
        except Exception as e:
            logger.error("Failed to get metrics", error=str(e))
            raise
    
    async def get_logs(
        self,
        log_group: str,
        start_time: str,
        end_time: str,
        filter_pattern: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get CloudWatch logs"""
        try:
            # Parse time strings to timestamps
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            start_timestamp = int(start_dt.timestamp() * 1000)
            end_timestamp = int(end_dt.timestamp() * 1000)
            
            # Build filter logs request
            request_params = {
                'logGroupName': log_group,
                'startTime': start_timestamp,
                'endTime': end_timestamp,
                'limit': limit
            }
            
            if filter_pattern:
                request_params['filterPattern'] = filter_pattern
            
            async with self.logs_client as logs:
                response = await logs.filter_log_events(**request_params)
            
            # Format response
            log_events = []
            for event in response.get('events', []):
                log_events.append({
                    'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                    'message': event['message'],
                    'log_stream': event.get('logStreamName', ''),
                    'event_id': event.get('eventId', '')
                })
            
            logger.info(
                "Retrieved logs",
                log_group=log_group,
                count=len(log_events)
            )
            
            return log_events
            
        except Exception as e:
            logger.error("Failed to get logs", error=str(e))
            raise
    
    async def list_log_groups(self, prefix: Optional[str] = None) -> List[str]:
        """List available log groups"""
        try:
            request_params = {}
            if prefix:
                request_params['logGroupNamePrefix'] = prefix
            
            async with self.logs_client as logs:
                response = await logs.describe_log_groups(**request_params)
            
            log_groups = [
                group['logGroupName']
                for group in response.get('logGroups', [])
            ]
            
            logger.info("Listed log groups", count=len(log_groups))
            return log_groups
            
        except Exception as e:
            logger.error("Failed to list log groups", error=str(e))
            raise
    
    async def list_metrics(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available metrics"""
        try:
            request_params = {}
            if namespace:
                request_params['Namespace'] = namespace
            
            async with self.cloudwatch_client as cw:
                response = await cw.list_metrics(**request_params)
            
            metrics = []
            for metric in response.get('Metrics', []):
                metrics.append({
                    'namespace': metric['Namespace'],
                    'metric_name': metric['MetricName'],
                    'dimensions': {
                        dim['Name']: dim['Value']
                        for dim in metric.get('Dimensions', [])
                    }
                })
            
            logger.info("Listed metrics", count=len(metrics))
            return metrics
            
        except Exception as e:
            logger.error("Failed to list metrics", error=str(e))
            raise
    
    async def get_rds_metrics(self, db_instance_identifier: str) -> Dict[str, Any]:
        """Get RDS-specific metrics for database monitoring"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            
            # Common RDS metrics
            rds_metrics = [
                'CPUUtilization',
                'DatabaseConnections',
                'FreeableMemory',
                'ReadLatency',
                'WriteLatency',
                'ReadIOPS',
                'WriteIOPS'
            ]
            
            metrics_data = {}
            
            for metric_name in rds_metrics:
                try:
                    datapoints = await self.get_metrics(
                        namespace='AWS/RDS',
                        metric_name=metric_name,
                        dimensions={'DBInstanceIdentifier': db_instance_identifier},
                        start_time=start_time.isoformat(),
                        end_time=end_time.isoformat(),
                        period=300
                    )
                    metrics_data[metric_name] = datapoints
                except Exception as e:
                    logger.warning(f"Failed to get {metric_name}", error=str(e))
                    metrics_data[metric_name] = []
            
            logger.info(
                "Retrieved RDS metrics",
                db_instance=db_instance_identifier,
                metrics_count=len(metrics_data)
            )
            
            return metrics_data
            
        except Exception as e:
            logger.error("Failed to get RDS metrics", error=str(e))
            raise