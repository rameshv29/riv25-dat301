#!/usr/bin/env python3
"""
IDR MCP Server
Provides incident management and knowledge base retrieval tools via MCP protocol
"""

import os
import json
import boto3
from typing import Optional
from mcp.server import Server
from mcp.types import Tool, TextContent
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'dat301-ws-incidents')
IDR_CLUSTER_ARN = os.environ.get('IDR_CLUSTER_ARN', '')
IDR_SECRET_ARN = os.environ.get('IDR_SECRET_ARN', '')
IDR_DATABASE_NAME = os.environ.get('IDR_DATABASE_NAME', 'idr_db')

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
rds_data = boto3.client('rds-data', region_name=AWS_REGION)
bedrock_runtime = boto3.client('bedrock-runtime', region_name=AWS_REGION)

# Create MCP server
app = Server("idr-mcp-server")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available IDR tools"""
    return [
        Tool(
            name="list_incidents",
            description="List all incidents from DynamoDB. Optionally filter by status (OPEN, IN_PROGRESS, RESOLVED, CLOSED).",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: OPEN, IN_PROGRESS, RESOLVED, or CLOSED",
                        "enum": ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]
                    }
                }
            }
        ),
        Tool(
            name="get_incident_details",
            description="Get detailed information about a specific incident by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "incident_id": {
                        "type": "string",
                        "description": "The incident ID (e.g., INC-12345678)"
                    }
                },
                "required": ["incident_id"]
            }
        ),
        Tool(
            name="update_incident_status",
            description="Update the status of an incident. Use this after remediating an incident.",
            inputSchema={
                "type": "object",
                "properties": {
                    "incident_id": {
                        "type": "string",
                        "description": "The incident ID to update"
                    },
                    "status": {
                        "type": "string",
                        "description": "New status",
                        "enum": ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]
                    },
                    "resolution": {
                        "type": "string",
                        "description": "Resolution notes (optional)"
                    }
                },
                "required": ["incident_id", "status"]
            }
        ),
        Tool(
            name="search_kb_runbooks",
            description="Search the knowledge base for remediation runbooks using vector similarity. Returns relevant runbooks for the given query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'high CPU remediation', 'IOPS troubleshooting')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 3)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    
    try:
        if name == "list_incidents":
            return await list_incidents(arguments.get("status"))
        
        elif name == "get_incident_details":
            return await get_incident_details(arguments["incident_id"])
        
        elif name == "update_incident_status":
            return await update_incident_status(
                arguments["incident_id"],
                arguments["status"],
                arguments.get("resolution")
            )
        
        elif name == "search_kb_runbooks":
            return await search_kb_runbooks(
                arguments["query"],
                arguments.get("limit", 3)
            )
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        logger.error(f"Error in {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def list_incidents(status: Optional[str] = None) -> list[TextContent]:
    """List incidents from DynamoDB"""
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        
        if status:
            response = table.scan(
                FilterExpression='incident_status = :status',
                ExpressionAttributeValues={':status': status}
            )
        else:
            response = table.scan()
        
        incidents = response.get('Items', [])
        
        if not incidents:
            return [TextContent(type="text", text="No incidents found.")]
        
        result = f"Found {len(incidents)} incidents:\n\n"
        for inc in incidents:
            result += f"**{inc.get('incident_id', 'N/A')}**\n"
            result += f"- Type: {inc.get('incident_type', 'Unknown')}\n"
            result += f"- Status: {inc.get('incident_status', 'Unknown')}\n"
            result += f"- Alarm: {inc.get('alarm_name', 'N/A')}\n"
            result += f"- Reason: {inc.get('alarm_reason', 'N/A')}\n"
            result += f"- Created: {inc.get('created_at', 'N/A')}\n\n"
        
        return [TextContent(type="text", text=result)]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing incidents: {str(e)}")]

async def get_incident_details(incident_id: str) -> list[TextContent]:
    """Get incident details"""
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        
        # Query using pk
        response = table.query(
            KeyConditionExpression='pk = :pk',
            ExpressionAttributeValues={':pk': f'INCIDENT#{incident_id}'}
        )
        
        items = response.get('Items', [])
        if not items:
            return [TextContent(type="text", text=f"Incident {incident_id} not found.")]
        
        incident = items[0]
        result = json.dumps(incident, indent=2, default=str)
        return [TextContent(type="text", text=result)]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error getting incident: {str(e)}")]

async def update_incident_status(incident_id: str, status: str, resolution: Optional[str] = None) -> list[TextContent]:
    """Update incident status"""
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        
        # First get the item to find the sk
        response = table.query(
            KeyConditionExpression='pk = :pk',
            ExpressionAttributeValues={':pk': f'INCIDENT#{incident_id}'}
        )
        
        items = response.get('Items', [])
        if not items:
            return [TextContent(type="text", text=f"Incident {incident_id} not found.")]
        
        sk = items[0]['sk']
        
        from datetime import datetime
        update_expr = 'SET incident_status = :status, updated_at = :updated_at'
        expr_values = {
            ':status': status,
            ':updated_at': datetime.utcnow().isoformat()
        }
        
        if resolution:
            update_expr += ', resolution = :resolution'
            expr_values[':resolution'] = resolution
        
        table.update_item(
            Key={'pk': f'INCIDENT#{incident_id}', 'sk': sk},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )
        
        return [TextContent(type="text", text=f"Successfully updated incident {incident_id} to status {status}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error updating incident: {str(e)}")]

async def search_kb_runbooks(query: str, limit: int = 3) -> list[TextContent]:
    """Search knowledge base using pgvector"""
    try:
        # Get embedding
        response = bedrock_runtime.invoke_model(
            modelId='amazon.titan-embed-text-v2:0',
            body=json.dumps({"inputText": query})
        )
        result = json.loads(response['body'].read())
        embedding = result['embedding']
        
        # Search pgvector
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        sql = f"""
        SELECT text, metadata, 
               embedding <=> '{embedding_str}'::vector AS distance
        FROM idr_knowledge
        ORDER BY distance
        LIMIT {limit}
        """
        
        response = rds_data.execute_statement(
            resourceArn=IDR_CLUSTER_ARN,
            secretArn=IDR_SECRET_ARN,
            database=IDR_DATABASE_NAME,
            sql=sql
        )
        
        if not response.get('records'):
            return [TextContent(type="text", text="No runbooks found in knowledge base.")]
        
        result_text = f"Found {len(response['records'])} relevant runbooks:\n\n"
        for i, record in enumerate(response['records'], 1):
            text = record[0]['stringValue']
            distance = float(record[2]['doubleValue'])
            similarity = 1 - distance
            
            result_text += f"**Runbook {i}** (Similarity: {similarity:.2%})\n"
            result_text += f"{text}\n\n"
            result_text += "---\n\n"
        
        return [TextContent(type="text", text=result_text)]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error searching knowledge base: {str(e)}")]

async def main():
    """Run the MCP server"""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
