#!/usr/bin/env python3
"""
Health check script for CloudWatch MCP Transport Wrapper

This script is used by Docker's HEALTHCHECK instruction to verify
that the transport wrapper is running and healthy.
"""

import sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def main():
    """Perform health check"""
    try:
        # Configure requests with retry strategy
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        
        # Make health check request to MCP server
        # Try the root endpoint first, then a simple MCP request
        try:
            response = session.get("http://localhost:8000/", timeout=5)
        except:
            # If root doesn't work, try a simple MCP initialize request
            response = session.post(
                "http://localhost:8000/",
                json={
                    "jsonrpc": "2.0",
                    "id": "health-check",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "health-check", "version": "1.0.0"}
                    }
                },
                headers={"Content-Type": "application/json"},
                timeout=5
            )
        
        if response.status_code == 200:
            print("Health check passed")
            sys.exit(0)
        else:
            print(f"Health check failed with status {response.status_code}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"Health check failed with error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error during health check: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()