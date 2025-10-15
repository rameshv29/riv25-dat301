#!/bin/bash
# Health check script for pgvector KB MCP server

# Check if the health endpoint responds
curl -f http://localhost:8000/health || exit 1