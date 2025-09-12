#!/usr/bin/env python3
"""
CloudWatch MCP Server
Provides CloudWatch metrics and logs access via Model Context Protocol
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import boto3
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .cloudwatch_tools import CloudWatchTools
from .mcp_handler import MCPHandler

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Configuration
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Global instances
cloudwatch_tools: Optional[CloudWatchTools] = None
mcp_handler: Optional[MCPHandler] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global cloudwatch_tools, mcp_handler
    
    logger.info("Starting CloudWatch MCP Server", port=MCP_PORT, region=AWS_REGION)
    
    try:
        # Initialize CloudWatch tools
        cloudwatch_tools = CloudWatchTools(region=AWS_REGION)
        await cloudwatch_tools.initialize()
        
        # Initialize MCP handler
        mcp_handler = MCPHandler(cloudwatch_tools)
        
        logger.info("CloudWatch MCP Server initialized successfully")
        yield
        
    except Exception as e:
        logger.error("Failed to initialize CloudWatch MCP Server", error=str(e))
        raise
    finally:
        logger.info("Shutting down CloudWatch MCP Server")
        if cloudwatch_tools:
            await cloudwatch_tools.cleanup()


# Create FastAPI app
app = FastAPI(
    title="CloudWatch MCP Server",
    description="Model Context Protocol server for AWS CloudWatch integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class HealthResponse(BaseModel):
    status: str
    version: str
    region: str


class MetricsRequest(BaseModel):
    namespace: str
    metric_name: str
    dimensions: Optional[Dict[str, str]] = None
    start_time: str
    end_time: str
    period: int = 300


class LogsRequest(BaseModel):
    log_group: str
    start_time: str
    end_time: str
    filter_pattern: Optional[str] = None
    limit: int = 100


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        region=AWS_REGION
    )


# CloudWatch health check
@app.get("/cloudwatch/health")
async def cloudwatch_health():
    """CloudWatch service health check"""
    if not cloudwatch_tools:
        raise HTTPException(status_code=503, detail="CloudWatch tools not initialized")
    
    try:
        # Test CloudWatch connectivity
        is_healthy = await cloudwatch_tools.health_check()
        if is_healthy:
            return {"status": "healthy", "service": "cloudwatch"}
        else:
            raise HTTPException(status_code=503, detail="CloudWatch service unavailable")
    except Exception as e:
        logger.error("CloudWatch health check failed", error=str(e))
        raise HTTPException(status_code=503, detail=f"CloudWatch health check failed: {str(e)}")


# MCP endpoints
@app.post("/mcp/tools/list")
async def list_tools():
    """List available MCP tools"""
    if not mcp_handler:
        raise HTTPException(status_code=503, detail="MCP handler not initialized")
    
    return await mcp_handler.list_tools()


@app.post("/mcp/tools/call")
async def call_tool(request: dict):
    """Call an MCP tool"""
    if not mcp_handler:
        raise HTTPException(status_code=503, detail="MCP handler not initialized")
    
    return await mcp_handler.call_tool(request)


# CloudWatch specific endpoints
@app.post("/cloudwatch/metrics")
async def get_metrics(request: MetricsRequest):
    """Get CloudWatch metrics"""
    if not cloudwatch_tools:
        raise HTTPException(status_code=503, detail="CloudWatch tools not initialized")
    
    try:
        metrics = await cloudwatch_tools.get_metrics(
            namespace=request.namespace,
            metric_name=request.metric_name,
            dimensions=request.dimensions,
            start_time=request.start_time,
            end_time=request.end_time,
            period=request.period
        )
        return {"metrics": metrics}
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@app.post("/cloudwatch/logs")
async def get_logs(request: LogsRequest):
    """Get CloudWatch logs"""
    if not cloudwatch_tools:
        raise HTTPException(status_code=503, detail="CloudWatch tools not initialized")
    
    try:
        logs = await cloudwatch_tools.get_logs(
            log_group=request.log_group,
            start_time=request.start_time,
            end_time=request.end_time,
            filter_pattern=request.filter_pattern,
            limit=request.limit
        )
        return {"logs": logs}
    except Exception as e:
        logger.error("Failed to get logs", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting CloudWatch MCP Server", host=MCP_HOST, port=MCP_PORT)
    
    uvicorn.run(
        "main:app",
        host=MCP_HOST,
        port=MCP_PORT,
        log_level="info",
        access_log=True,
        reload=False
    )