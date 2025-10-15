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

# Create non-root user first
RUN useradd --create-home --shell /bin/bash app

# Change ownership of the app directory
RUN chown -R app:app /app

# Copy project files and set ownership
COPY --chown=app:app pyproject.toml ./

# Switch to app user for dependency installation
USER app

# Install dependencies using uv
RUN uv sync --no-dev

# Copy source code with proper ownership
COPY --chown=app:app awslabs/ ./awslabs/

# Switch back to root to copy health check script
USER root
COPY docker-healthcheck.sh /docker-healthcheck.sh
RUN chmod +x /docker-healthcheck.sh

# Switch back to app user for runtime
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