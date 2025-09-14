#!/usr/bin/env python3
"""
Transport Wrapper for AWS Labs CloudWatch MCP Server

This wrapper provides HTTP transport for the AWS Labs CloudWatch MCP server,
allowing it to be deployed as a containerized service behind a load balancer.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="CloudWatch MCP Transport Wrapper")

# Global variables for MCP server process
mcp_process: Optional[subprocess.Popen] = None
mcp_client: Optional[httpx.AsyncClient] = None

class MCPTransportWrapper:
    """Wrapper class to manage MCP server process and HTTP transport"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.client: Optional[httpx.AsyncClient] = None
        self.server_url = "http://localhost:3000"  # AWS Labs MCP server default port
        
    async def start_mcp_server(self):
        """Start the AWS Labs CloudWatch MCP server"""
        try:
            # Start the AWS Labs CloudWatch MCP server
            cmd = [
                sys.executable, "-m", "mcp_server_aws.cloudwatch",
                "--port", "3000",
                "--host", "127.0.0.1"
            ]
            
            logger.info(f"Starting MCP server with command: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a moment for the server to start
            await asyncio.sleep(2)
            
            # Check if process is still running
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                logger.error(f"MCP server failed to start. stdout: {stdout}, stderr: {stderr}")
                raise RuntimeError("MCP server failed to start")
            
            # Create HTTP client for communicating with MCP server
            self.client = httpx.AsyncClient(timeout=30.0)
            
            logger.info("MCP server started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise
    
    async def stop_mcp_server(self):
        """Stop the MCP server process"""
        if self.client:
            await self.client.aclose()
            self.client = None
            
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None
            
        logger.info("MCP server stopped")
    
    async def forward_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Forward MCP request to the underlying server"""
        if not self.client:
            raise HTTPException(status_code=503, detail="MCP server not available")
        
        try:
            response = await self.client.post(
                f"{self.server_url}/mcp",
                json=request_data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"MCP server returned status {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"MCP server error: {response.text}"
                )
                
        except httpx.RequestError as e:
            logger.error(f"Request to MCP server failed: {e}")
            raise HTTPException(status_code=503, detail="MCP server unavailable")

# Global wrapper instance
wrapper = MCPTransportWrapper()

@app.on_event("startup")
async def startup_event():
    """Start the MCP server on application startup"""
    await wrapper.start_mcp_server()

@app.on_event("shutdown")
async def shutdown_event():
    """Stop the MCP server on application shutdown"""
    await wrapper.stop_mcp_server()

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer"""
    try:
        # Check if MCP server process is running
        if not wrapper.process or wrapper.process.poll() is not None:
            raise HTTPException(status_code=503, detail="MCP server not running")
        
        # Try to ping the MCP server
        if wrapper.client:
            try:
                response = await wrapper.client.get(f"{wrapper.server_url}/health", timeout=5.0)
                if response.status_code != 200:
                    raise HTTPException(status_code=503, detail="MCP server unhealthy")
            except httpx.RequestError:
                # If health endpoint doesn't exist, that's okay for AWS Labs server
                pass
        
        return {"status": "healthy", "service": "cloudwatch-mcp-wrapper"}
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """Main MCP protocol endpoint"""
    try:
        # Parse request body
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="Empty request body")
        
        try:
            request_data = json.loads(body)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
        
        # Validate basic JSON-RPC structure
        if not isinstance(request_data, dict) or "jsonrpc" not in request_data:
            raise HTTPException(status_code=400, detail="Invalid JSON-RPC request")
        
        # Forward to MCP server
        response_data = await wrapper.forward_request(request_data)
        
        return JSONResponse(
            content=response_data,
            headers={
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Accept"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": "server-error",
                "error": {
                    "code": -32603,
                    "message": f"Internal server error: {str(e)}"
                }
            },
            status_code=500
        )

@app.options("/mcp")
async def mcp_options():
    """Handle CORS preflight requests"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept"
        }
    )

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "CloudWatch MCP Transport Wrapper",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "mcp": "/mcp"
        },
        "status": "running"
    }

if __name__ == "__main__":
    # Configuration from environment variables
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    
    logger.info(f"Starting CloudWatch MCP Transport Wrapper on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )