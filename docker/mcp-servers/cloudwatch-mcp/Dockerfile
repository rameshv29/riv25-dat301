# CloudWatch MCP Server Dockerfile - Transport Wrapper Approach
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including git
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Clone the AWS Labs MCP repository
RUN git clone https://github.com/awslabs/mcp.git /tmp/mcp-server-aws

# Install the CloudWatch MCP server from AWS Labs
RUN cd /tmp/mcp-server-aws && pip install -e .

# Copy our transport wrapper requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy our transport wrapper and health check
COPY transport_wrapper.py .
COPY health_check.py .

# Create non-root user
RUN useradd --create-home --shell /bin/bash mcp-user && \
    chown -R mcp-user:mcp-user /app

USER mcp-user

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python /app/health_check.py

# Run the transport wrapper
CMD ["python", "transport_wrapper.py"]
