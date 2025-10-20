#!/bin/bash
echo "🐍 DAT301 Workshop - Python 3.11.13 + PostgreSQL Setup"

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

# Add pg_config to PATH
echo 'export PATH="/usr/pgsql-16/bin:$PATH"' >> /home/ec2-user/.bashrc
echo 'export PATH="/usr/pgsql-16/bin:$PATH"' >> /root/.bashrc
export PATH="/usr/pgsql-16/bin:$PATH"

# Install pyenv
if [ ! -d "/home/ec2-user/.pyenv" ]; then
    curl https://pyenv.run | bash
    chown -R ec2-user:ec2-user /home/ec2-user/.pyenv
fi

# Configure pyenv for ec2-user
cat >> /home/ec2-user/.bashrc << 'EOF'
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
EOF

# Install Python 3.11.13 as ec2-user
sudo -u ec2-user bash << 'EOF'
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
pyenv install 3.11.13
pyenv global 3.11.13
EOF

echo "✅ Python 3.11.13 and PostgreSQL setup completed"