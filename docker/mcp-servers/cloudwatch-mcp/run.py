#!/usr/bin/env python3
"""
Runner script for AWS Labs CloudWatch MCP Server

This script starts the AWS Labs CloudWatch MCP server using FastMCP's
streamable_http transport on port 8000 for containerized deployment.
"""

import subprocess
import sys
import os

def main():
    """Start the AWS Labs CloudWatch MCP server with HTTP transport"""
    try:
        # Set up environment
        env = os.environ.copy()
        
        # Run the AWS Labs CloudWatch MCP server with streamable_http transport
        cmd = [
            "python", "-m", "cloudwatch_mcp_server",
            "--transport", "streamable_http",
            "--port", "8000",
            "--host", "0.0.0.0"
        ]
        
        print(f"Starting AWS Labs CloudWatch MCP server: {' '.join(cmd)}")
        
        # Execute the server
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
        
    except KeyboardInterrupt:
        print("\nShutting down CloudWatch MCP server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting CloudWatch MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()