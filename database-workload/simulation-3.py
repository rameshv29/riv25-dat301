import psycopg2
from concurrent.futures import ThreadPoolExecutor
import time
from dotenv import load_dotenv
import os
import sys
from datetime import datetime

# Load environment variables
load_dotenv()

# Get database parameters
db_params = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT')
}

def log_message(session, message):
    """Helper function to print timestamped log messages"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {session}: {message}")

def run_query(iteration):
    """Execute multiple queries in single transaction"""
    conn = psycopg2.connect(**db_params)
    conn.autocommit = False  # Ensure we're in a transaction
    cur = conn.cursor()
    try:
        cur.execute("SET statement_timeout = '300s';")
        cur.execute("BEGIN;")
        
        log_message(f"Session {iteration}", "Starting transaction...")
        
        query = """
        SELECT count(*) 
        FROM generate_series(1, 10000) a, 
             generate_series(1, 100000) b 
        WHERE a > b;
        """
        
        # Run query multiple times in same transaction
        for i in range(3):
            log_message(f"Session {iteration}", f"Executing query {i+1}/5...")
            cur.execute(query)
            result = cur.fetchone()
            log_message(f"Session {iteration}", f"Query {i+1} completed: {result[0]} rows")
        
        conn.commit()
        log_message(f"Session {iteration}", "Transaction committed")
        
    except Exception as e:
        log_message(f"Session {iteration}", f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def main():
    num_connections = int(os.getenv('NUM_CONNECTIONS', 2))
    
    log_message("Main", f"Starting with {num_connections} parallel connections")
    
    try:
        with ThreadPoolExecutor(max_workers=num_connections) as executor:
            futures = [
                executor.submit(run_query, i+1)
                for i in range(num_connections)
            ]
            
            for future in futures:
                future.result()
        
        log_message("Main", "All queries completed")
        
    except KeyboardInterrupt:
        log_message("Main", "Received interrupt signal")
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()
