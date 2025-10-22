#!/bin/bash
echo "📦 DAT301 Workshop - Python Dependencies Setup (Safe Mode)"

# Install uv for ec2-user (not root)
sudo -u ec2-user bash << 'EOF'
cd /home/ec2-user
curl -LsSf https://astral.sh/uv/install.sh | sh
EOF

# Set up Python environment as ec2-user
sudo -u ec2-user bash << 'EOF'
cd /workshop

# Load pyenv environment
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Verify we're using the right Python
echo "Using Python: $(python --version)"
echo "Python path: $(which python)"

# Create virtual environment with pyenv Python 3.11.13
python -m venv .venv
source .venv/bin/activate

# Verify virtual environment
echo "Venv Python: $(python --version)"
echo "Venv pip: $(which pip)"

# Install core dependencies
pip install --upgrade pip
pip install streamlit boto3 psycopg2-binary pydantic fastapi uvicorn python-jose[cryptography] loguru httpx python-multipart pandas plotly mcp

# Install MCP servers
pip install postgres-mcp-server cloudwatch-mcp-server

echo "✅ Virtual environment created with Python 3.11.13"
EOF

# Install MCP servers globally with uv for ec2-user
sudo -u ec2-user bash << 'EOF'
export PATH="$HOME/.local/bin:$PATH"
if [ -f "$HOME/.local/bin/uv" ]; then
    uv tool install postgres-mcp-server || echo "MCP server install failed, but available in venv"
    uv tool install cloudwatch-mcp-server || echo "MCP server install failed, but available in venv"
fi
EOF

echo "✅ Python dependencies setup completed safely"