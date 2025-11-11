#!/bin/bash
echo "🗄️ DAT301 Workshop - Database Setup"

# Check if main database connection variables are set
if [ -z "$MAIN_HOST" ] || [ -z "$MAIN_DB" ] || [ -z "$MAIN_USER" ] || [ -z "$MAIN_PASS" ]; then
    echo "❌ Error: Main database environment variables not set"
    echo "   Required: MAIN_HOST, MAIN_DB, MAIN_USER, MAIN_PASS"
    exit 1
fi

echo "📊 Connecting to: $MAIN_DB on $MAIN_HOST"

# Set PostgreSQL environment variables
export PGHOST=$MAIN_HOST
export PGPORT=${MAIN_PORT:-5432}
export PGDATABASE=$MAIN_DB
export PGUSER=$MAIN_USER
export PGPASSWORD=$MAIN_PASS

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="$SCRIPT_DIR/database"

# Check if SQL scripts directory exists
if [ ! -d "$SQL_DIR" ]; then
    echo "❌ Error: SQL scripts directory not found: $SQL_DIR"
    exit 1
fi

# Run SQL scripts in order
echo "📝 Executing database setup scripts..."
for script in "$SQL_DIR"/*.sql; do
    if [ -f "$script" ]; then
        echo "  → Running: $(basename $script)"
        psql -f "$script" 2>&1 | grep -v "already exists" | grep -v "NOTICE" || {
            echo "  ⚠️  Warning: $(basename $script) may have failed or already applied"
        }
    fi
done

# Unset password
unset PGPASSWORD

echo "✅ Database setup completed!"
