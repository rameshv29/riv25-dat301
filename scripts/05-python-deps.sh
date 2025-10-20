#!/bin/bash
echo "📦 DAT301 Workshop - Python Dependencies Setup"

cd /workshop

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.cargo/bin:$PATH"

# Set up Python environment
export PYENV_ROOT="/root/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Create virtual environment in /workshop
cd /workshop
python -m venv .venv
source .venv/bin/activate

# Install core dependencies
pip install --upgrade pip
pip install streamlit boto3 psycopg2-binary pydantic fastapi uvicorn python-jose[cryptography] loguru httpx python-multipart pandas plotly mcp

# Install MCP servers
pip install postgres-mcp-server cloudwatch-mcp-server

# Set ownership to ec2-user
chown -R ec2-user:ec2-user /workshop/.venv

# Install MCP servers globally with uv (fallback)
if [ -f /root/.cargo/bin/uv ]; then
    /root/.cargo/bin/uv tool install postgres-mcp-server || echo "MCP server already installed"
    /root/.cargo/bin/uv tool install cloudwatch-mcp-server || echo "MCP server already installed"
fi

echo "✅ Python dependencies setup completed"