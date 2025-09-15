# CloudWatch MCP Server Dockerfile - AWS Labs Direct Approach
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including git
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Clone the AWS Labs MCP repository and install CloudWatch MCP server
RUN git clone https://github.com/awslabs/mcp.git /tmp/mcp && \
    cd /tmp/mcp/src/cloudwatch-mcp-server && \
    pip install -e . && \
    cd /app && \
    rm -rf /tmp/mcp

# Copy application files
COPY health_check.py run.py ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash mcp-user && \
    chown -R mcp-user:mcp-user /app

USER mcp-user

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python /app/health_check.py

# Run the AWS Labs CloudWatch MCP server with HTTP transport
CMD ["python", "/app/run.py"]