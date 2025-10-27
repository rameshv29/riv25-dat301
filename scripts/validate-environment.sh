#!/bin/bash
echo "🔍 DAT301 Workshop - Environment Validation"
echo "============================================"

ERRORS=0
WARNINGS=0

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✅ $1${NC}"
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
    ((ERRORS++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++))
}

echo ""
echo "1. System Python Check"
echo "----------------------"
SYSTEM_PYTHON=$(/usr/bin/python3 --version 2>&1)
if [[ $SYSTEM_PYTHON == *"3.9"* ]]; then
    check_pass "System Python intact: $SYSTEM_PYTHON"
else
    check_warn "System Python version unexpected: $SYSTEM_PYTHON (expected 3.9.x)"
fi

echo ""
echo "2. DNF/YUM Check"
echo "----------------"
if dnf --version &> /dev/null; then
    check_pass "DNF working correctly"
else
    check_fail "DNF not working - system Python may be broken"
fi

echo ""
echo "3. Pyenv Installation"
echo "---------------------"
if sudo -u ec2-user bash -c '[ -d "$HOME/.pyenv" ]'; then
    check_pass "Pyenv installed in user space"
    PYENV_PYTHON=$(sudo -u ec2-user bash -c 'export PYENV_ROOT="$HOME/.pyenv" && export PATH="$PYENV_ROOT/bin:$PATH" && eval "$(pyenv init -)" && cd /workshop && python --version 2>&1')
    if [[ $PYENV_PYTHON == *"3.11.13"* ]]; then
        check_pass "Workshop Python: $PYENV_PYTHON"
    else
        check_warn "Workshop Python version: $PYENV_PYTHON (expected 3.11.13)"
    fi
else
    check_fail "Pyenv not installed"
fi

echo ""
echo "4. Q CLI Installation"
echo "---------------------"
if command -v q &> /dev/null; then
    Q_VERSION=$(q --version 2>&1 | head -1)
    check_pass "Q CLI installed: $Q_VERSION"
else
    check_fail "Q CLI not installed"
fi

echo ""
echo "5. UV Installation"
echo "------------------"
if sudo -u ec2-user bash -c '[ -f "$HOME/.local/bin/uv" ]'; then
    UV_VERSION=$(sudo -u ec2-user bash -c '$HOME/.local/bin/uv --version 2>&1')
    check_pass "UV installed: $UV_VERSION"
    
    if sudo -u ec2-user bash -c 'grep -q ".local/bin" ~/.bashrc'; then
        check_pass "UV in PATH (.bashrc)"
    else
        check_warn "UV not in PATH - may not be accessible in all contexts"
    fi
else
    check_fail "UV not installed"
fi

echo ""
echo "6. PostgreSQL Installation"
echo "--------------------------"
if command -v psql &> /dev/null; then
    PG_VERSION=$(psql --version)
    check_pass "PostgreSQL installed: $PG_VERSION"
else
    check_fail "PostgreSQL not installed"
fi

if [ -f /usr/pgsql-16/bin/pg_config ]; then
    check_pass "PostgreSQL 16 development files installed"
else
    check_warn "PostgreSQL 16 development files may be missing"
fi

echo ""
echo "7. Code Server Installation"
echo "---------------------------"
if [ -f /usr/bin/code-server ]; then
    CODE_VERSION=$(code-server --version 2>&1 | head -1)
    check_pass "Code Server installed: $CODE_VERSION"
else
    check_fail "Code Server not installed"
fi

if [ -f /etc/systemd/system/code-server.service ]; then
    check_pass "Code Server systemd service configured"
    
    if systemctl is-active --quiet code-server; then
        check_pass "Code Server service running"
    else
        check_warn "Code Server service not running"
    fi
else
    check_fail "Code Server systemd service not configured"
fi

echo ""
echo "8. Workshop Directory"
echo "---------------------"
if [ -d /workshop ]; then
    check_pass "Workshop directory exists"
    
    if [ -f /workshop/.python-version ]; then
        PYENV_LOCAL=$(cat /workshop/.python-version)
        if [[ $PYENV_LOCAL == "3.11.13" ]]; then
            check_pass "Pyenv local version set: $PYENV_LOCAL"
        else
            check_warn "Pyenv local version: $PYENV_LOCAL (expected 3.11.13)"
        fi
    else
        check_warn "Pyenv local version not set in /workshop"
    fi
    
    if [ -d /workshop/.venv ]; then
        check_pass "Virtual environment exists"
    else
        check_warn "Virtual environment not created"
    fi
else
    check_fail "Workshop directory does not exist"
fi

echo ""
echo "9. AWS CLI"
echo "----------"
if command -v aws &> /dev/null; then
    AWS_VERSION=$(aws --version 2>&1)
    check_pass "AWS CLI installed: $AWS_VERSION"
else
    check_fail "AWS CLI not installed"
fi

echo ""
echo "10. Node.js"
echo "-----------"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    check_pass "Node.js installed: $NODE_VERSION"
else
    check_warn "Node.js not installed"
fi

echo ""
echo "11. Git"
echo "-------"
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version)
    check_pass "Git installed: $GIT_VERSION"
else
    check_fail "Git not installed"
fi

echo ""
echo "12. Environment Variables"
echo "-------------------------"
if [ -f /workshop/.env ]; then
    check_pass ".env file exists"
    
    if grep -q "AWS_REGION" /workshop/.env; then
        check_pass "AWS_REGION configured"
    else
        check_warn "AWS_REGION not in .env"
    fi
else
    check_warn ".env file not created"
fi

echo ""
echo "============================================"
echo "Validation Summary"
echo "============================================"
echo -e "Errors: ${RED}$ERRORS${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ Environment validation passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Environment validation failed with $ERRORS error(s)${NC}"
    exit 1
fi
