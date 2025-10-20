#!/bin/bash
echo "🔧 DAT301 Workshop - System Setup"

# Update system
dnf update -y

# Fix curl conflicts
dnf remove -y curl-minimal || true

# Install basic packages
dnf install -y git wget unzip jq
dnf groupinstall -y "Development Tools"

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install
ln -sf /usr/local/bin/aws /usr/bin/aws
rm -rf awscliv2.zip aws/

# Install Node.js
curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
dnf install -y nodejs

echo "✅ System setup completed"