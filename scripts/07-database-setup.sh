#!/bin/bash
echo "🗄️ DAT301 Workshop - Database Setup Scripts"

# Create database scripts directory
mkdir -p /workshop/database

# Copy SQL scripts from repo to workshop directory
echo "📋 Copying database setup scripts..."

# Copy all SQL files from scripts/database/ to /workshop/database/
if [ -d /workshop/scripts/database ]; then
    cp /workshop/scripts/database/*.sql /workshop/database/ 2>/dev/null || true
fi

# Create master setup script
cat > /workshop/database/setup.sh << 'EOF'
#!/bin/bash
set -e

echo "🗄️ Setting up workshop database..."

# Use PG* environment variables (set by /etc/profile.d/workshop-env.sh)
# PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD

# Check if variables are set
if [ -z "$PGHOST" ] || [ -z "$PGDATABASE" ] || [ -z "$PGUSER" ]; then
    echo "❌ Error: Database environment variables not set"
    echo "   Run: source /etc/profile.d/workshop-env.sh"
    exit 1
fi

echo "📊 Database: $PGDATABASE on $PGHOST"

# Run SQL scripts in order
for script in /workshop/database/*.sql; do
    if [ -f "$script" ]; then
        echo "📝 Executing: $(basename $script)"
        psql -f "$script" 2>&1 || {
            echo "⚠️  Warning: $(basename $script) failed or already applied"
        }
    fi
done

echo "✅ Database setup completed!"
EOF

chmod +x /workshop/database/setup.sh
chown -R ec2-user:ec2-user /workshop/database

echo "✅ Database setup scripts created in /workshop/database/"
echo "   Run: /workshop/database/setup.sh"
