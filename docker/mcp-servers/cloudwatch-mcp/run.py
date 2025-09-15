#!/usr/bin/env python3
"""
HTTP wrapper for AWS Labs CloudWatch MCP Server
"""

import asyncio
import json
import logging
import subprocess
import sys
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CloudWatch MCP HTTP Wrapper")

# Global MCP process
mcp_process = None

async def start_mcp_server():
    """Start the AWS Labs CloudWatch MCP server with stdio"""
    global mcp_process
    try:
        # Start the MCP server with stdio transport
        mcp_process = subprocess.Popen(
            ["python", "-m", "awslabs.cloudwatch_mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info("AWS Labs CloudWatch MCP server started")
        return True
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        return False

async def send_mcp_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send request to MCP server via stdio"""
    global mcp_process
    
    if not mcp_process or mcp_process.poll() is not None:
        raise HTTPException(status_code=503, detail="MCP server not available")
    
    try:
        # Send request
        request_json = json.dumps(request_data) + '\n'
        mcp_process.stdin.write(request_json)
        mcp_process.stdin.flush()
        
        # Read response
        response_line = mcp_process.stdout.readline()
        if not response_line:
            raise HTTPException(status_code=503, detail="No response from MCP server")
        
        return json.loads(response_line.strip())
    except Exception as e:
        logger.error(f"Error communicating with MCP server: {e}")
        raise HTTPException(status_code=503, detail="MCP server communication error")

@app.on_event("startup")
async def startup_event():
    """Start MCP server on startup"""
    success = await start_mcp_server()
    if not success:
        logger.error("Failed to start MCP server during startup")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global mcp_process
    if mcp_process and mcp_process.poll() is None:
        return {"status": "healthy", "service": "cloudwatch-mcp-wrapper"}
    else:
        raise HTTPException(status_code=503, detail="MCP server not running")

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP protocol endpoint"""
    try:
        body = await request.body()
        request_data = json.loads(body)
        response_data = await send_mcp_request(request_data)
        return JSONResponse(content=response_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "CloudWatch MCP HTTP Wrapper",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "mcp": "/mcp"
        }
    }

if __name__ == "__main__":
    print("Starting CloudWatch MCP HTTP Wrapper on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")