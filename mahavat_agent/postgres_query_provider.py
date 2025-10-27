#!/usr/bin/env python3
"""
Postgres Query Provider MCP Server
Provides PostgreSQL diagnostic queries and workflows that can be executed
through the PostgreSQL MCP server's run_query tool.
"""
import json
import boto3
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Optional

mcp = FastMCP("Postgres-Query-Provider")

@mcp.tool()
def list_available_workflows() -> list[dict]:
    """
    List all available diagnostic workflows in the Postgres Query Provider.
    
    Returns:
        List of available workflow functions with descriptions
    """
    return [
        {
            "name": "vacuum_analysis_diagnostic",
            "description": "Comprehensive vacuum and bloat analysis workflow",
            "use_case": "Check vacuum status, identify bloated tables, analyze autovacuum settings"
        },
        {
            "name": "lock_analysis_diagnostic", 
            "description": "Database lock contention analysis workflow",
            "use_case": "Identify blocking queries, analyze lock waits and contention"
        },
        {
            "name": "slow_query_diagnostic",
            "description": "Slow query performance analysis workflow", 
            "use_case": "Identify slow queries, analyze query performance patterns"
        },
        {
            "name": "connection_analysis_diagnostic",
            "description": "Database connection and session analysis workflow",
            "use_case": "Analyze connections, identify long-running transactions"
        }
    ]

class PostgreSQLRunbooks:
    """PostgreSQL diagnostic runbooks with predefined queries"""

    @staticmethod
    def get_slow_query_diagnostic(DatabaseInstance: Optional[str] = None) -> List[Dict[str, str]]:
        """Returns diagnostic steps for slow query analysis"""
        return [
            {
                "step": "Check currently running slow queries using pg_stat_activity",
                "tool": "run_query",
                "action": "Identify currently running queries where the state is 'active' and query_start is older than 5 minutes",
                "query": """
                    SELECT datname, pid, usename, application_name, client_addr, state, 
                    EXTRACT(EPOCH FROM (now() - query_start))::integer AS duration_seconds, query 
                    FROM pg_stat_activity 
                    WHERE backend_type = 'client backend' AND state = 'active' 
                    AND EXTRACT(EPOCH FROM (now() - query_start)) > 300
                    ORDER BY duration_seconds DESC;
                """,
                "DatabaseInstance": DatabaseInstance
            },
            {
                "step": "Identify top SQL queries by execution time per call",
                "tool": "run_query", 
                "action": "Use pg_stat_statements to identify top SQL queries by total execution time per call",
                "query": """
                    SELECT query, total_time, calls, (total_time / calls) AS avg_time 
                    FROM pg_stat_statements 
                    ORDER BY avg_time DESC 
                    LIMIT 10;
                """,
                "DatabaseInstance": DatabaseInstance
            }
        ]

    @staticmethod
    def get_lock_analysis_diagnostic(DatabaseInstance: Optional[str] = None) -> List[Dict[str, str]]:
        """Returns diagnostic steps for lock contention analysis"""
        return [
            {
                "step": "Check current locks and blocking queries",
                "tool": "run_query",
                "action": "Identify current locks and which queries are blocking others",
                "query": """
                    SELECT 
                        blocked_locks.pid AS blocked_pid,
                        blocked_activity.usename AS blocked_user,
                        blocking_locks.pid AS blocking_pid,
                        blocking_activity.usename AS blocking_user,
                        blocked_activity.query AS blocked_statement,
                        blocking_activity.query AS current_statement_in_blocking_process,
                        blocked_activity.application_name AS blocked_application,
                        blocking_activity.application_name AS blocking_application
                    FROM pg_catalog.pg_locks blocked_locks
                    JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
                    JOIN pg_catalog.pg_locks blocking_locks 
                        ON blocking_locks.locktype = blocked_locks.locktype
                        AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
                        AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
                        AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
                        AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
                        AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
                        AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
                        AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
                        AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
                        AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
                        AND blocking_locks.pid != blocked_locks.pid
                    JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
                    WHERE NOT blocked_locks.granted;
                """,
                "DatabaseInstance": DatabaseInstance
            },
            {
                "step": "Check lock wait events and durations",
                "tool": "run_query",
                "action": "Analyze current lock wait events and their durations",
                "query": """
                    SELECT 
                        pid,
                        usename,
                        application_name,
                        state,
                        wait_event_type,
                        wait_event,
                        EXTRACT(EPOCH FROM (now() - query_start))::integer AS query_duration_seconds,
                        query
                    FROM pg_stat_activity 
                    WHERE wait_event_type = 'Lock' 
                    AND state = 'active'
                    ORDER BY query_duration_seconds DESC;
                """,
                "DatabaseInstance": DatabaseInstance
            }
        ]

    @staticmethod
    def get_vacuum_analysis_diagnostic(DatabaseInstance: Optional[str] = None) -> List[Dict[str, str]]:
        """Returns diagnostic steps for vacuum and bloat analysis"""
        return [
            {
                "step": "Check current vacuum progress",
                "tool": "run_query",
                "action": "Monitor current vacuum operations and their progress",
                "query": """
                    SELECT 
                        p.pid,
                        EXTRACT(EPOCH FROM (now() - a.xact_start))::integer AS duration_seconds,
                        p.datname AS database,
                        CASE 
                            WHEN p.relid IS NOT NULL THEN p.relid::regclass::text
                            ELSE 'N/A'
                        END AS table_name,
                        p.phase,
                        a.query,
                        round(100.0 * p.heap_blks_scanned / p.heap_blks_total, 1) AS scanned_pct,
                        round(100.0 * p.heap_blks_vacuumed / p.heap_blks_total, 1) AS vacuumed_pct
                    FROM pg_stat_progress_vacuum p 
                    JOIN pg_stat_activity a USING (pid)
                    ORDER BY duration_seconds DESC;
                """,
                "DatabaseInstance": DatabaseInstance
            },
            {
                "step": "Check tables with high dead tuple ratio",
                "tool": "run_query",
                "action": "Identify tables with more than 20% dead tuples indicating bloat",
                "query": """
                    SELECT 
                        schemaname, 
                        relname, 
                        last_vacuum, 
                        last_autovacuum, 
                        n_live_tup, 
                        n_dead_tup, 
                        round((n_dead_tup::numeric/nullif(n_live_tup+n_dead_tup,0))* 100,2) AS dead_tuple_percent
                    FROM pg_stat_user_tables 
                    WHERE n_dead_tup::float/nullif(n_live_tup+n_dead_tup,0) > 0.2 
                    ORDER BY n_live_tup DESC;
                """,
                "DatabaseInstance": DatabaseInstance
            },
            {
                "step": "Check replication slots blocking vacuum",
                "tool": "run_query",
                "action": "Identify inactive or lagging replication slots that may prevent vacuum from reclaiming space",
                "query": """
                    SELECT 
                        slot_name,
                        slot_type,
                        database,
                        active,
                        xmin,
                        catalog_xmin,
                        restart_lsn,
                        confirmed_flush_lsn,
                        CASE 
                            WHEN xmin IS NOT NULL THEN age(xmin)
                            ELSE NULL
                        END as xmin_age,
                        CASE 
                            WHEN catalog_xmin IS NOT NULL THEN age(catalog_xmin)
                            ELSE NULL
                        END as catalog_xmin_age,
                        CASE
                            WHEN NOT active THEN 'INACTIVE - Slot not in use'
                            WHEN age(xmin) > 1000000 THEN 'CRITICAL - Blocking vacuum (xmin age > 1M)'
                            WHEN age(catalog_xmin) > 1000000 THEN 'CRITICAL - Blocking vacuum (catalog_xmin age > 1M)'
                            WHEN age(xmin) > 100000 THEN 'WARNING - High xmin age (> 100K)'
                            WHEN age(catalog_xmin) > 100000 THEN 'WARNING - High catalog_xmin age (> 100K)'
                            ELSE 'OK'
                        END as status
                    FROM pg_replication_slots
                    ORDER BY GREATEST(
                        COALESCE(age(xmin), 0), 
                        COALESCE(age(catalog_xmin), 0)
                    ) DESC;
                """,
                "DatabaseInstance": DatabaseInstance
            }
        ]

    @staticmethod
    def get_connection_analysis_diagnostic(DatabaseInstance: Optional[str] = None) -> List[Dict[str, str]]:
        """Returns diagnostic steps for connection and session analysis"""
        return [
            {
                "step": "Check active connections by state and application",
                "tool": "run_query",
                "action": "Analyze current database connections grouped by state and application",
                "query": """
                    SELECT 
                        state,
                        application_name,
                        count(*) as connection_count,
                        EXTRACT(EPOCH FROM max(now() - query_start))::integer as max_query_duration_seconds,
                        EXTRACT(EPOCH FROM max(now() - state_change))::integer as max_state_duration_seconds
                    FROM pg_stat_activity 
                    WHERE backend_type = 'client backend'
                    GROUP BY state, application_name 
                    ORDER BY connection_count DESC;
                """,
                "DatabaseInstance": DatabaseInstance
            },
            {
                "step": "Check long-running transactions",
                "tool": "run_query", 
                "action": "Identify long-running transactions that may be blocking autovacuum",
                "query": """
                    SELECT 
                        pid,
                        datname AS database_name,
                        usename AS username,
                        application_name,
                        state,
                        EXTRACT(EPOCH FROM (now() - xact_start))::integer AS transaction_duration_seconds,
                        EXTRACT(EPOCH FROM (now() - query_start))::integer AS query_duration_seconds,
                        xact_start AS transaction_start_time,
                        wait_event_type,
                        wait_event,
                        LEFT(query, 100) AS query_preview
                    FROM pg_stat_activity
                    WHERE state != 'idle'
                    AND xact_start IS NOT NULL
                    AND backend_type = 'client backend'
                    AND pid != pg_backend_pid()
                    ORDER BY transaction_duration DESC
                    LIMIT 15;
                """,
                "DatabaseInstance": DatabaseInstance
            }
        ]

# Register runbook tools
@mcp.tool()
def slow_query_diagnostic(DatabaseInstance: str = "dev-cluster") -> List[Dict[str, str]]:
    """Get diagnostic steps for slow query analysis"""
    return PostgreSQLRunbooks.get_slow_query_diagnostic(DatabaseInstance)

@mcp.tool()
def lock_analysis_diagnostic(DatabaseInstance: str = "dev-cluster") -> List[Dict[str, str]]:
    """Get diagnostic steps for lock contention analysis"""
    return PostgreSQLRunbooks.get_lock_analysis_diagnostic(DatabaseInstance)

@mcp.tool()
def vacuum_analysis_diagnostic(DatabaseInstance: str = "dev-cluster") -> List[Dict[str, str]]:
    """Get diagnostic steps for vacuum and bloat analysis"""
    return PostgreSQLRunbooks.get_vacuum_analysis_diagnostic(DatabaseInstance)

@mcp.tool()
def connection_analysis_diagnostic(DatabaseInstance: str = "dev-cluster") -> List[Dict[str, str]]:
    """Get diagnostic steps for connection and session analysis"""
    return PostgreSQLRunbooks.get_connection_analysis_diagnostic(DatabaseInstance)

@mcp.tool()
def execute_diagnostic_step(step_data: dict) -> dict:
    """
    Execute a diagnostic step by returning the query to be run by PostgreSQL MCP server
    
    Args:
        step_data: Dictionary containing step information with 'query' key
    
    Returns:
        Dictionary with query and execution instructions
    """
    if 'query' not in step_data:
        return {"error": "No query found in step data"}
    
    return {
        "tool_to_use": "run_query",
        "sql_query": step_data['query'],
        "step_description": step_data.get('action', 'Execute diagnostic query'),
        "instructions": f"Execute this query using the PostgreSQL MCP server's run_query tool: {step_data['query']}"
    }

if __name__ == "__main__":
    mcp.run()
