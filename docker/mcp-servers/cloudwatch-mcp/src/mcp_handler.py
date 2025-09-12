"""
MCP Protocol Handler for CloudWatch Tools
Implements Model Context Protocol for CloudWatch integration
"""

from typing import Dict, List, Any, Optional
import json
from datetime import datetime, timedelta

import structlog

from .cloudwatch_tools import CloudWatchTools

logger = structlog.get_logger()


class MCPHandler:
    """MCP protocol handler for CloudWatch tools"""
    
    def __init__(self, cloudwatch_tools: CloudWatchTools):
        self.cloudwatch_tools = cloudwatch_tools
        self.tools = self._define_tools()
    
    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define available MCP tools"""
        return {
            "get_cloudwatch_metrics": {
                "name": "get_cloudwatch_metrics",
                "description": "Get CloudWatch metrics for monitoring AWS resources",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "CloudWatch namespace (e.g., AWS/RDS, AWS/EC2)"
                        },
                        "metric_name": {
                            "type": "string",
                            "description": "Name of the metric to retrieve"
                        },
                        "dimensions": {
                            "type": "object",
                            "description": "Dimensions to filter the metric (optional)",
                            "additionalProperties": {"type": "string"}
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Start time in ISO format (optional, defaults to 1 hour ago)"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "End time in ISO format (optional, defaults to now)"
                        },
                        "period": {
                            "type": "integer",
                            "description": "Period in seconds (optional, defaults to 300)"
                        }
                    },
                    "required": ["namespace", "metric_name"]
                }
            },
            "get_cloudwatch_logs": {
                "name": "get_cloudwatch_logs",
                "description": "Get CloudWatch logs for troubleshooting and analysis",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "log_group": {
                            "type": "string",
                            "description": "CloudWatch log group name"
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Start time in ISO format (optional, defaults to 1 hour ago)"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "End time in ISO format (optional, defaults to now)"
                        },
                        "filter_pattern": {
                            "type": "string",
                            "description": "Filter pattern for log events (optional)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of log events to return (optional, defaults to 100)"
                        }
                    },
                    "required": ["log_group"]
                }
            },
            "get_rds_performance_metrics": {
                "name": "get_rds_performance_metrics",
                "description": "Get comprehensive RDS performance metrics for database analysis",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "db_instance_identifier": {
                            "type": "string",
                            "description": "RDS database instance identifier"
                        },
                        "time_range_hours": {
                            "type": "integer",
                            "description": "Time range in hours to look back (optional, defaults to 1)"
                        }
                    },
                    "required": ["db_instance_identifier"]
                }
            },
            "list_cloudwatch_metrics": {
                "name": "list_cloudwatch_metrics",
                "description": "List available CloudWatch metrics",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "namespace": {
                            "type": "string",
                            "description": "CloudWatch namespace to filter by (optional)"
                        }
                    }
                }
            },
            "list_log_groups": {
                "name": "list_log_groups",
                "description": "List available CloudWatch log groups",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prefix": {
                            "type": "string",
                            "description": "Log group name prefix to filter by (optional)"
                        }
                    }
                }
            }
        }
    
    async def list_tools(self) -> Dict[str, Any]:
        """List available MCP tools"""
        tools_list = [
            {
                "name": tool_name,
                "description": tool_def["description"],
                "inputSchema": tool_def["inputSchema"]
            }
            for tool_name, tool_def in self.tools.items()
        ]
        
        return {
            "tools": tools_list
        }
    
    async def call_tool(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool"""
        try:
            tool_name = request.get("name")
            arguments = request.get("arguments", {})
            
            if tool_name not in self.tools:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Unknown tool: {tool_name}"
                        }
                    ],
                    "isError": True
                }
            
            # Route to appropriate handler
            if tool_name == "get_cloudwatch_metrics":
                result = await self._handle_get_metrics(arguments)
            elif tool_name == "get_cloudwatch_logs":
                result = await self._handle_get_logs(arguments)
            elif tool_name == "get_rds_performance_metrics":
                result = await self._handle_get_rds_metrics(arguments)
            elif tool_name == "list_cloudwatch_metrics":
                result = await self._handle_list_metrics(arguments)
            elif tool_name == "list_log_groups":
                result = await self._handle_list_log_groups(arguments)
            else:
                result = {"error": f"Handler not implemented for tool: {tool_name}"}
            
            # Format response
            if "error" in result:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: {result['error']}"
                        }
                    ],
                    "isError": True
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, default=str)
                        }
                    ]
                }
                
        except Exception as e:
            logger.error("Tool call failed", tool=tool_name, error=str(e))
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Tool execution failed: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _handle_get_metrics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_cloudwatch_metrics tool call"""
        try:
            # Set default time range if not provided
            if "start_time" not in arguments or "end_time" not in arguments:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=1)
                arguments.setdefault("start_time", start_time.isoformat())
                arguments.setdefault("end_time", end_time.isoformat())
            
            arguments.setdefault("period", 300)
            
            metrics = await self.cloudwatch_tools.get_metrics(**arguments)
            
            return {
                "metrics": metrics,
                "summary": {
                    "namespace": arguments["namespace"],
                    "metric_name": arguments["metric_name"],
                    "data_points": len(metrics),
                    "time_range": f"{arguments['start_time']} to {arguments['end_time']}"
                }
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_get_logs(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_cloudwatch_logs tool call"""
        try:
            # Set default time range if not provided
            if "start_time" not in arguments or "end_time" not in arguments:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=1)
                arguments.setdefault("start_time", start_time.isoformat())
                arguments.setdefault("end_time", end_time.isoformat())
            
            arguments.setdefault("limit", 100)
            
            logs = await self.cloudwatch_tools.get_logs(**arguments)
            
            return {
                "logs": logs,
                "summary": {
                    "log_group": arguments["log_group"],
                    "log_events": len(logs),
                    "time_range": f"{arguments['start_time']} to {arguments['end_time']}",
                    "filter_pattern": arguments.get("filter_pattern", "None")
                }
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_get_rds_metrics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_rds_performance_metrics tool call"""
        try:
            db_instance = arguments["db_instance_identifier"]
            
            metrics = await self.cloudwatch_tools.get_rds_metrics(db_instance)
            
            # Calculate summary statistics
            summary = {}
            for metric_name, datapoints in metrics.items():
                if datapoints:
                    values = [point["value"] for point in datapoints]
                    summary[metric_name] = {
                        "latest": values[-1] if values else 0,
                        "average": sum(values) / len(values) if values else 0,
                        "max": max(values) if values else 0,
                        "min": min(values) if values else 0,
                        "data_points": len(values)
                    }
                else:
                    summary[metric_name] = {
                        "latest": 0,
                        "average": 0,
                        "max": 0,
                        "min": 0,
                        "data_points": 0
                    }
            
            return {
                "db_instance": db_instance,
                "metrics": metrics,
                "summary": summary
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_list_metrics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_cloudwatch_metrics tool call"""
        try:
            namespace = arguments.get("namespace")
            metrics = await self.cloudwatch_tools.list_metrics(namespace)
            
            return {
                "metrics": metrics,
                "count": len(metrics),
                "namespace_filter": namespace or "All namespaces"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_list_log_groups(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_log_groups tool call"""
        try:
            prefix = arguments.get("prefix")
            log_groups = await self.cloudwatch_tools.list_log_groups(prefix)
            
            return {
                "log_groups": log_groups,
                "count": len(log_groups),
                "prefix_filter": prefix or "No prefix filter"
            }
            
        except Exception as e:
            return {"error": str(e)}