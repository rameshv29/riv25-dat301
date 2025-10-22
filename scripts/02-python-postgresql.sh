#!/bin/bash
echo "🐍 DAT301 Workshop - Python 3.11.13 + PostgreSQL Setup (Safe Mode)"

# IMPORTANT: Keep system Python (3.9) untouched for dnf/yum
echo "📋 System Python will remain: $(python3 --version)"

# Install build dependencies
dnf install -y \
    openssl-devel \
    bzip2-devel \
    libffi-devel \
    zlib-devel \
    readline-devel \
    sqlite-devel \
    ncurses-devel \
    xz-devel \
    tk-devel \
    gdbm-devel \
    libuuid-devel \
    expat-devel

# Install PostgreSQL 16
dnf install -y postgresql16-server postgresql16 postgresql16-devel postgresql16-contrib

# Add pg_config to PATH for ec2-user only (not system-wide)
echo 'export PATH="/usr/pgsql-16/bin:$PATH"' >> /home/ec2-user/.bashrc

# Create workshop directory first
mkdir -p /workshop
chown ec2-user:ec2-user /workshop

# Install pyenv for ec2-user only (user-space installation)
sudo -u ec2-user bash << 'EOF'
cd /home/ec2-user

# Install pyenv in user directory
if [ ! -d "$HOME/.pyenv" ]; then
    curl https://pyenv.run | bash
fi

# Configure pyenv for this user only (avoid duplicates)
if ! grep -q "PYENV_ROOT" ~/.bashrc; then
    cat >> ~/.bashrc << 'PYENV_EOF'
# Pyenv configuration (user-only, does not affect system Python)
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
PYENV_EOF
fi

# Load pyenv for current session
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Install Python 3.11.13 (user-only)
pyenv install 3.11.13 || echo "Python 3.11.13 already installed"

# Set local Python version for workshop directory
cd /workshop
pyenv local 3.11.13

echo "✅ Python 3.11.13 installed for user ec2-user only"
EOF

# Verify system Python is still intact
echo "🔍 Verification:"
echo "System Python: $(/usr/bin/python3 --version)"
echo "DNF status: $(dnf --version | head -1)"

echo "✅ Python 3.11.13 and PostgreSQL setup completed safely"