# Use Python 3.11 slim image
FROM public.ecr.aws/docker/library/python:3.11-slim@sha256:ad48727987b259854d52241fac3bc633574364867b8e20aec305e6e7f4028b26

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install uv

# Copy project files
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv sync --no-dev

# Copy source code
COPY awslabs/ ./awslabs/

# Copy health check script
COPY docker-healthcheck.sh /docker-healthcheck.sh
RUN chmod +x /docker-healthcheck.sh

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Set environment variables
ENV PYTHONPATH=/app
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /docker-healthcheck.sh

# Expose port
EXPOSE 8000

# Run the MCP server
CMD ["uv", "run", "python", "-m", "awslabs.pgvector_kb_mcp_server.server"]