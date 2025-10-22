#!/bin/bash
echo "💻 DAT301 Workshop - Code Server Setup"

# Install code-server
export HOME=/root
curl -fsSL https://code-server.dev/install.sh | bash

# Verify installation
if [ ! -f /usr/bin/code-server ]; then
    echo "Code-server installation failed, trying alternative method..."
    curl -fL https://github.com/coder/code-server/releases/download/v4.105.0/code-server-4.105.0-amd64.rpm -o /tmp/code-server.rpm
    rpm -i /tmp/code-server.rpm
fi

# Configure code-server for ec2-user
mkdir -p /home/ec2-user/.config/code-server
cat > /home/ec2-user/.config/code-server/config.yaml << EOF
bind-addr: 0.0.0.0:8080
auth: password
password: ${CODE_EDITOR_PASSWORD:-TempPass123!}
cert: false
disable-telemetry: true
disable-update-check: true
disable-workspace-trust: true
disable-file-downloads: false
EOF

# Create systemd service for code-server
cat > /etc/systemd/system/code-server.service << EOF
[Unit]
Description=code-server
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/workshop
Environment=PYENV_ROOT=/home/ec2-user/.pyenv
Environment=PATH=/home/ec2-user/.pyenv/bin:/home/ec2-user/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStartPre=/bin/bash -c 'eval "$(pyenv init -)"'
ExecStart=/usr/bin/code-server --bind-addr 0.0.0.0:8080 --auth password
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Set ownership
chown -R ec2-user:ec2-user /home/ec2-user/

echo "✅ Code Server setup completed"