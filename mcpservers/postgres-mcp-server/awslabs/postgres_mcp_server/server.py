# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""awslabs postgres MCP Server implementation."""

import argparse
import asyncio
import sys
from awslabs.postgres_mcp_server.connection import DBConnectionSingleton
from awslabs.postgres_mcp_server.connection.psycopg_pool_connection import PsycopgPoolConnection
from awslabs.postgres_mcp_server.mutable_sql_detector import (
    check_sql_injection_risk,
    detect_mutating_keywords,
)
from botocore.exceptions import BotoCoreError, ClientError
from loguru import logger
from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field
from starlette.responses import PlainTextResponse
from starlette.requests import Request
from typing import Annotated, Any, Dict, List, Optional


client_error_code_key = 'run_query ClientError code'
unexpected_error_key = 'run_query unexpected error'
write_query_prohibited_key = 'Your MCP tool only allows readonly query. If you want to write, change the MCP configuration per README.md'
query_comment_prohibited_key = 'The comment in query is prohibited because of injection risk'
query_injection_risk_key = 'Your query contains risky injection patterns'


class DummyCtx:
    """A dummy context class for error handling in MCP tools."""

    async def error(self, message):
        """Raise a runtime error with the given message.

        Args:
            message: The error message to include in the runtime error
        """
        # Do nothing
        pass


def extract_cell(cell: dict):
    """Extracts the scalar or array value from a single cell."""
    if cell.get('isNull'):
        return None
    for key in (
        'stringValue',
        'longValue',
        'doubleValue',
        'booleanValue',
        'blobValue',
        'arrayValue',
    ):
        if key in cell:
            return cell[key]
    return None


def parse_execute_response(response: dict) -> list[dict]:
    """Convert RDS Data API execute_statement response to list of rows."""
    columns = [col['name'] for col in response.get('columnMetadata', [])]
    records = []

    for row in response.get('records', []):
        row_data = {col: extract_cell(cell) for col, cell in zip(columns, row)}
        records.append(row_data)

    return records


mcp = FastMCP(
    'pg-mcp MCP server. This is the starting point for all solutions created',
    dependencies=[
        'loguru',
    ],
)

# Global variable to store the direct database connection
_global_db_connection = None

# Add health check endpoint for ALB health checks
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check endpoint for load balancer."""
    return PlainTextResponse("OK")




@mcp.tool(name='run_query', description='Run a SQL query against PostgreSQL')
async def run_query(
    sql: Annotated[str, Field(description='The SQL query to run')],
    ctx: Context,
    db_connection=None,
    query_parameters: Annotated[
        Optional[List[Dict[str, Any]]], Field(description='Parameters for the SQL query')
    ] = None,
) -> list[dict]:  # type: ignore
    """Run a SQL query against PostgreSQL.

    Args:
        sql: The sql statement to run
        ctx: MCP context for logging and state management
        db_connection: DB connection object passed by unit test. It should be None if called by MCP server.
        query_parameters: Parameters for the SQL query

    Returns:
        List of dictionary that contains query response rows
    """
    global client_error_code_key
    global unexpected_error_key
    global write_query_prohibited_key

    if db_connection is None:
        try:
            # Try to get the connection from the singleton (for RDS Data API)
            db_connection = DBConnectionSingleton.get().db_connection
        except RuntimeError:
            # If the singleton is not initialized, try the global direct connection
            global _global_db_connection
            if _global_db_connection is not None:
                db_connection = _global_db_connection
            else:
                logger.error('No database connection available')
                await ctx.error('No database connection available')
                return [{'error': 'No database connection available'}]

    if db_connection is None:
        raise AssertionError('db_connection should never be None')

    if db_connection.readonly_query:
        matches = detect_mutating_keywords(sql)
        if (bool)(matches):
            logger.info(
                f'query is rejected because current setting only allows readonly query. detected keywords: {matches}, SQL query: {sql}'
            )
            await ctx.error(write_query_prohibited_key)
            return [{'error': write_query_prohibited_key}]

    issues = check_sql_injection_risk(sql)
    if issues:
        logger.info(
            f'query is rejected because it contains risky SQL pattern, SQL query: {sql}, reasons: {issues}'
        )
        await ctx.error(
            str({'message': 'Query parameter contains suspicious pattern', 'details': issues})
        )
        return [{'error': query_injection_risk_key}]

    try:
        logger.info(f'run_query: readonly:{db_connection.readonly_query}, SQL:{sql}')

        # Execute the query using the abstract connection interface
        response = await db_connection.execute_query(sql, query_parameters)

        logger.success(f'run_query successfully executed query:{sql}')
        return parse_execute_response(response)
    except ClientError as e:
        logger.exception(client_error_code_key)
        await ctx.error(
            str({'code': e.response['Error']['Code'], 'message': e.response['Error']['Message']})
        )
        return [{'error': client_error_code_key}]
    except Exception as e:
        logger.exception(unexpected_error_key)
        error_details = f'{type(e).__name__}: {str(e)}'
        await ctx.error(str({'message': error_details}))
        return [{'error': unexpected_error_key}]


@mcp.tool(
    name='get_table_schema',
    description='Fetch table columns and comments from Postgres',
)
async def get_table_schema(
    table_name: Annotated[str, Field(description='name of the table')], ctx: Context
) -> list[dict]:
    """Get a table's schema information given the table name.

    Args:
        table_name: name of the table
        ctx: MCP context for logging and state management

    Returns:
        List of dictionary that contains query response rows
    """
    logger.info(f'get_table_schema: {table_name}')

    sql = """
        SELECT
            a.attname AS column_name,
            pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
            col_description(a.attrelid, a.attnum) AS column_comment
        FROM
            pg_attribute a
        WHERE
            a.attrelid = to_regclass(:table_name)
            AND a.attnum > 0
            AND NOT a.attisdropped
        ORDER BY a.attnum
    """

    params = [{'name': 'table_name', 'value': {'stringValue': table_name}}]

    return await run_query(sql=sql, ctx=ctx, query_parameters=params)


# ===== PostgreSQL Diagnostic Tools =====
# Based on runbooks.py - PostgreSQL-only tools (CloudWatch tools skipped)

@mcp.tool(
    name='pg_stat_activity_slow_query_last_5mins',
    description='Check currently running slow queries using pg_stat_activity',
)
async def pg_stat_activity_slow_query_last_5mins(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Check currently running queries where the state is 'active' and query_start is older than 5 minutes."""
    logger.info(f'pg_stat_activity_slow_query_last_5mins: {database_instance}')

    sql = """
        SELECT datname, pid, usename, application_name, client_addr, state, 
        now() - query_start AS duration, query 
        FROM pg_stat_activity 
        WHERE backend_type = 'client backend' AND state = 'active' 
        AND query_start < now() - interval '5 minutes' 
        ORDER BY duration DESC;
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='pg_stat_statements',
    description='Identify top SQL queries by execution time per call',
)
async def pg_stat_statements(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Identify Top SQL Queries by its total execution time per call using pg_stat_statements."""
    logger.info(f'pg_stat_statements: {database_instance}')

    sql = """
        SELECT query, total_time, calls, (total_time / calls) AS avg_time 
        FROM pg_stat_statements 
        ORDER BY avg_time DESC 
        LIMIT 10;
    """

    try:
        return await run_query(sql=sql, ctx=ctx)
    except Exception as e:
        if "pg_stat_statements" in str(e):
            error_msg = "pg_stat_statements extension is not installed or enabled. Please install and configure the extension."
            logger.warning(error_msg)
            return [{'error': error_msg}]
        raise


@mcp.tool(
    name='get_vacuum_progress_current',
    description='Check current vacuum progress from PostgreSQL database',
)
async def get_vacuum_progress_current(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Check the current vacuum progress."""
    logger.info(f'get_vacuum_progress_current: {database_instance}')

    sql = """
        select CURRENT_TIMESTAMP as snapshot_time ,p.pid, now() - a.xact_start AS duration, coalesce(wait_event_type ||'.'|| wait_event, 'CPU') AS wait_event,
        CASE WHEN a.query ~ '^autovacuum.*to prevent wraparound' THEN 'wraparound' WHEN a.query ~ '^vacuum' THEN 'user' ELSE 'regular' END AS mode,
        p.datname AS database, p.relid::regclass AS table, p.phase, a.query ,
        pg_size_pretty(p.heap_blks_total * current_setting('block_size')::int) AS table_size,
        pg_size_pretty(pg_total_relation_size(p.relid)) AS total_size,
        pg_size_pretty(p.heap_blks_scanned * current_setting('block_size')::int) AS scanned,
        pg_size_pretty(p.heap_blks_vacuumed * current_setting('block_size')::int) AS vacuumed,
        round(100.0 * p.heap_blks_scanned / p.heap_blks_total, 1) AS scanned_pct,
        round(100.0 * p.heap_blks_vacuumed / p.heap_blks_total, 1) AS vacuumed_pct,
        p.index_vacuum_count,
        s.n_dead_tup as total_num_dead_tuples
        FROM pg_stat_progress_vacuum p JOIN pg_stat_activity a using (pid)
             join pg_stat_all_tables s on s.relid = p.relid
        ORDER BY now() - a.xact_start DESC;
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='oldest_xid_all_databases',
    description='Check Oldest XID age of all databases',
)
async def oldest_xid_all_databases(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Get oldest transaction ID across all databases in the cluster instance."""
    logger.info(f'oldest_xid_all_databases: {database_instance}')

    sql = "SELECT max(age(datfrozenxid)) AS oldest_xid FROM pg_database;"

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='oldest_xid_by_database',
    description='Check transaction id (XID) Wraparound and age of oldest transaction',
)
async def oldest_xid_by_database(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Identify the oldest transaction ID for each database and returns the top 5 databases with the highest XID age."""
    logger.info(f'oldest_xid_by_database: {database_instance}')

    sql = "SELECT datname, age(datfrozenxid) AS xid_age FROM pg_database ORDER BY xid_age DESC LIMIT 5;"

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='percent_towards_xid_wraparound',
    description='Check percent towards emergency autovacuum and transaction ID wraparound',
)
async def percent_towards_xid_wraparound(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Calculate the percentage progress towards emergency autovacuum and transaction ID (XID) wraparound across all databases."""
    logger.info(f'percent_towards_xid_wraparound: {database_instance}')

    sql = """
        WITH max_age AS (
            SELECT 2^31-1000000 as max_old_xid, setting AS autovacuum_freeze_max_age
            FROM pg_catalog.pg_settings WHERE name = 'autovacuum_freeze_max_age'
        ),
        per_database_stats AS (
            SELECT datname, m.max_old_xid::int, m.autovacuum_freeze_max_age::int,
                   age(d.datfrozenxid) AS oldest_current_xid
            FROM pg_catalog.pg_database d
            JOIN max_age m ON (True)
            WHERE d.datallowconn
        )
        SELECT max(oldest_current_xid) AS oldest_current_xid,
               max(ROUND(100*(oldest_current_xid/max_old_xid::float))) AS percent_towards_wraparound,
               max(ROUND(100*(oldest_current_xid/autovacuum_freeze_max_age::float))) AS percent_towards_emergency_autovac
        FROM per_database_stats;
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='tables_with_oldest_relfrozedxid',
    description='Identify tables with oldest relfrozenxid',
)
async def tables_with_oldest_relfrozedxid(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Identify the top 10 tables with the oldest relfrozenxid values, indicating which tables are most in need of vacuuming."""
    logger.info(f'tables_with_oldest_relfrozedxid: {database_instance}')

    sql = """
        SELECT c.oid::regclass AS table_name, age(c.relfrozenxid) AS xid_age, n.nspname AS schema_name 
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace 
        WHERE c.relkind = 'r' AND c.relfrozenxid != 0 
        ORDER BY xid_age DESC 
        LIMIT 10;
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='pg_stat_tables_vacuum_info',
    description='Check last vacuum time for multiple tables',
)
async def pg_stat_tables_vacuum_info(
    ctx: Context, 
    database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None,
    table_names: Annotated[Optional[str], Field(description='Comma-separated list of table names to check (leave empty for all tables)')] = None
) -> list[dict]:
    """Retrieve vacuum activity such as most recent vacuum timestamp, vacuum count and days since last vacuum for specified tables or all tables if none specified."""
    logger.info(f'pg_stat_tables_vacuum_info: {database_instance}, tables: {table_names}')

    table_names_filter = table_names or ''
    
    sql = f"""
        SELECT schemaname,
               relname AS table_name,
               last_vacuum,
               last_autovacuum,
               vacuum_count,
               autovacuum_count,
               EXTRACT(EPOCH FROM (NOW() - COALESCE(last_vacuum, last_autovacuum)))/86400 AS days_since_last_vacuum
        FROM pg_stat_all_tables 
        WHERE ('{table_names_filter}' = '' OR relname = ANY(string_to_array('{table_names_filter}', ',')))
          AND schemaname NOT IN ('information_schema', 'pg_catalog')
        ORDER BY days_since_last_vacuum DESC NULLS FIRST;
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='table_index_bloat_analysis',
    description='Check table and index bloat for specified tables',
)
async def table_index_bloat_analysis(
    ctx: Context, 
    database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None,
    table_name: Annotated[Optional[str], Field(description='Specific table name to analyze (leave empty to check all tables)')] = None
) -> list[dict]:
    """Execute a comprehensive bloat detection query that calculates table and index bloat percentages and wasted space."""
    logger.info(f'table_index_bloat_analysis: {database_instance}, table: {table_name}')

    sql = """
        WITH constants AS (
            SELECT current_setting('block_size')::numeric AS bs,
                23 AS hdr,
                4 AS ma
        ),
        bloat_info AS (
            SELECT schemaname,
                tablename,
                attname,
                null_frac,
                avg_width
            FROM pg_stats
            WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
        ),
        table_bloat AS (
            SELECT cc.relnamespace::regnamespace::text schemaname,
                cc.relname tablename,
                cc.reltuples,
                cc.relpages,
                bs,
                CEIL((cc.reltuples * (
                    (SELECT SUM( avg_width ) FROM bloat_info bi WHERE bi.tablename = cc.relname and bi.schemaname = cc.relnamespace::regnamespace::text) + 23
                )) / bs) AS expected_pages,
                cc.relpages - CEIL((cc.reltuples * (
                    (SELECT SUM(
                        CASE WHEN avg_width = -1 THEN 10
                                ELSE avg_width
                        END
                    ) FROM bloat_info bi WHERE bi.tablename = cc.relname and bi.schemaname = cc.relnamespace::regnamespace::text) + 23
                )) / bs) AS wasted_pages
            FROM constants,
                pg_class cc
            JOIN pg_namespace nn ON cc.relnamespace = nn.oid
            WHERE cc.relkind = 'r'
            AND nn.nspname NOT IN ('information_schema', 'pg_catalog')
            AND cc.reltuples > 0
        )
        SELECT schemaname AS schema_name,
           tablename AS table_name,
            reltuples::bigint AS estimated_rows,
            relpages AS actual_pages,
            expected_pages,
            wasted_pages,
            CASE WHEN relpages > 0
                    THEN ROUND((wasted_pages::numeric / relpages::numeric) * 100, 2)
                    ELSE 0
            END AS bloat_percentage,
            pg_size_pretty((wasted_pages * constants.bs)::bigint) AS wasted_space,
            pg_size_pretty((relpages * constants.bs)::bigint) AS table_size
        FROM table_bloat, constants
        WHERE  wasted_pages > 0
        ORDER BY wasted_pages DESC NULLS LAST
        LIMIT 20;
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='table_autovacuum_settings',
    description='Check autovacuum configuration for a given table',
)
async def table_autovacuum_settings(
    ctx: Context, 
    database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None,
    table_name: Annotated[str, Field(description='Name of the table to check autovacuum settings for')] = None
) -> list[dict]:
    """Retrieve table-specific autovacuum configuration parameters and compare them with global defaults."""
    logger.info(f'table_autovacuum_settings: {database_instance}, table: {table_name}')

    if not table_name:
        return [{'error': 'table_name parameter is required'}]

    sql = f"""
        SELECT n.nspname AS schemaname, c.relname AS tablename, 
        split_part(option, '=', 1) AS option_name, split_part(option, '=', 2) AS option_value 
        FROM  pg_class c JOIN  pg_namespace n ON c.relnamespace = n.oid 
        JOIN  LATERAL unnest(c.reloptions) AS option ON True 
        WHERE  c.relname = '{table_name}';
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='tables_eligible_for_vacuum',
    description='Check top 10 tables currently eligible for vacuum',
)
async def tables_eligible_for_vacuum(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Identify the top 10 tables that are currently eligible for vacuum based on dead tuples and autovacuum thresholds."""
    logger.info(f'tables_eligible_for_vacuum: {database_instance}')

    sql = """
        WITH vbt AS (SELECT setting AS autovacuum_vacuum_threshold FROM pg_settings WHERE name = 'autovacuum_vacuum_threshold'),
             vsf AS (SELECT setting AS autovacuum_vacuum_scale_factor FROM pg_settings WHERE name = 'autovacuum_vacuum_scale_factor'),
             fma AS (SELECT setting AS autovacuum_freeze_max_age FROM pg_settings WHERE name = 'autovacuum_freeze_max_age'),
             sto AS (
                SELECT opt_oid, split_part(setting, '=', 1) AS param, split_part(setting, '=', 2) AS value
                FROM (SELECT oid opt_oid, unnest(reloptions) setting FROM pg_class) opt
             )
        SELECT
            ns.nspname||'.'||c.relname AS relation,
            pg_size_pretty(pg_table_size(c.oid)) AS table_size,
            age(relfrozenxid) AS xid_age,
            coalesce(cfma.value::float, autovacuum_freeze_max_age::float) AS autovacuum_freeze_max_age,
            (coalesce(cvbt.value::float, autovacuum_vacuum_threshold::float) + coalesce(cvsf.value::float,autovacuum_vacuum_scale_factor::float) * c.reltuples) AS autovacuum_vacuum_tuples,
            n_dead_tup AS dead_tuples,
            cfav.value AS autovacuum_enabled
        FROM pg_class c
        JOIN pg_namespace ns ON ns.oid = c.relnamespace
        JOIN pg_stat_all_tables stat ON stat.relid = c.oid
        JOIN vbt ON (1=1) JOIN vsf ON (1=1) JOIN fma ON (1=1)
        LEFT JOIN sto cvbt ON cvbt.param = 'autovacuum_vacuum_threshold' AND c.oid = cvbt.opt_oid
        LEFT JOIN sto cvsf ON cvsf.param = 'autovacuum_vacuum_scale_factor' AND c.oid = cvsf.opt_oid
        LEFT JOIN sto cfma ON cfma.param = 'autovacuum_freeze_max_age' AND c.oid = cfma.opt_oid
        LEFT JOIN sto cfav ON cfav.param = 'autovacuum_enabled' AND c.oid = cfav.opt_oid
        WHERE c.relkind IN ('r', 't')
          AND (
            age(relfrozenxid) >= coalesce(cfma.value::float, autovacuum_freeze_max_age::float)
            OR
            coalesce(cvbt.value::float, autovacuum_vacuum_threshold::float) + coalesce(cvsf.value::float,autovacuum_vacuum_scale_factor::float) * c.reltuples <= n_dead_tup
          )
        ORDER BY age(relfrozenxid) DESC
        LIMIT 10;
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='tables_high_dead_tuple_ratio',
    description='Check tables with more than 20% dead tuples',
)
async def tables_high_dead_tuple_ratio(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Identify tables with more than 20% dead tuples, indicating potential bloat and need for vacuum attention."""
    logger.info(f'tables_high_dead_tuple_ratio: {database_instance}')

    sql = """
        SELECT schemaname, relname, last_vacuum, last_autovacuum, n_live_tup, n_dead_tup, 
        trunc((n_dead_tup::numeric/nullif(n_live_tup+n_dead_tup,0))* 100,2) AS n_dead_tup_percent 
        FROM pg_stat_user_tables 
        WHERE n_dead_tup::float/nullif(n_live_tup+n_dead_tup,0) > 0.2 
        ORDER BY n_live_tup DESC;
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='long_running_transactions',
    description='Check for long running transactions',
)
async def long_running_transactions(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Identify long-running transactions that may be blocking autovacuum or causing performance issues."""
    logger.info(f'long_running_transactions: {database_instance}')

    sql = """
        SELECT pid,
            datname AS database_name,
            usename AS username,
            application_name,
            state,
            now() - xact_start AS transaction_duration,
            now() - query_start AS query_duration,
            EXTRACT(EPOCH FROM (now() - xact_start)) AS transaction_duration_seconds,
            EXTRACT(EPOCH FROM (now() - query_start)) AS query_duration_seconds,
            xact_start AS transaction_start_time,
            query_start AS query_start_time,
            wait_event_type,
            wait_event,
            backend_type,
            CASE 
                WHEN LENGTH(query) > 100 THEN LEFT(query, 100) || '...'
                ELSE query
            END AS query_preview,
            query AS full_query
        FROM pg_stat_activity
        WHERE state != 'idle'
        AND xact_start IS NOT NULL
        AND backend_type = 'client backend'
        AND pid != pg_backend_pid()  -- Exclude current session
        ORDER BY transaction_duration DESC
        LIMIT 15;
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='inactive_replication_slots',
    description='Check for inactive replication slots',
)
async def inactive_replication_slots(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Identify inactive replication slots that may be preventing WAL cleanup and causing disk space issues."""
    logger.info(f'inactive_replication_slots: {database_instance}')

    sql = """
        SELECT slot_name,
            slot_type,
            database,
            active,
            active_pid,
            restart_lsn::text,
            confirmed_flush_lsn::text,
            wal_status,
            safe_wal_size,
            two_phase,
            temporary,
            CASE 
                WHEN active = false AND restart_lsn IS NOT NULL THEN 
                    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn))
                ELSE 'N/A'
            END AS wal_lag_size,
            CASE 
                WHEN active = false AND restart_lsn IS NOT NULL THEN 
                    pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
                ELSE 0
            END AS wal_lag_bytes,
            CASE 
                WHEN active = false THEN 'Inactive - may prevent WAL cleanup'
                WHEN wal_status = 'lost' THEN 'WAL files lost - slot may be broken'
                WHEN wal_status = 'unreserved' THEN 'WAL not reserved - potential issue'
                ELSE 'Active and healthy'
            END AS status_description,
            -- Estimate potential disk space that could be freed
            CASE 
                WHEN active = false AND restart_lsn IS NOT NULL THEN
                    'Potential space savings: ' || pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn))
                ELSE 'No immediate space impact'
            END AS space_impact
        FROM pg_replication_slots
        ORDER BY 
            CASE WHEN active = false THEN 0 ELSE 1 END,
            wal_lag_bytes DESC NULLS LAST;
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='prepared_transactions_check',
    description='Check for orphaned prepared transactions',
)
async def prepared_transactions_check(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Monitor all prepared transactions and identify potential issues."""
    logger.info(f'prepared_transactions_check: {database_instance}')

    sql = """
        SELECT transaction::text, gid, prepared, owner, database 
        FROM pg_prepared_xacts 
        WHERE prepared < now() - interval '15 minutes';
    """

    return await run_query(sql=sql, ctx=ctx)


@mcp.tool(
    name='pg_stat_statements_by_calls',
    description='Identify top SQL queries by number of calls',
)
async def pg_stat_statements_by_calls(
    ctx: Context, database_instance: Annotated[Optional[str], Field(description='Database instance identifier')] = None
) -> list[dict]:
    """Identify top queries by its number of calls using pg_stat_statements."""
    logger.info(f'pg_stat_statements_by_calls: {database_instance}')

    sql = """
        SELECT query, calls, total_time, (total_time / calls) AS avg_time 
        FROM pg_stat_statements 
        ORDER BY calls DESC 
        LIMIT 10;
    """

    try:
        return await run_query(sql=sql, ctx=ctx)
    except Exception as e:
        if "pg_stat_statements" in str(e):
            error_msg = "pg_stat_statements extension is not installed or enabled. Please install and configure the extension."
            logger.warning(error_msg)
            return [{'error': error_msg}]
        raise


def main():
    """Main entry point for the MCP server application."""
    global client_error_code_key

    """Run the MCP server with CLI argument support."""
    parser = argparse.ArgumentParser(
        description='An AWS Labs Model Context Protocol (MCP) server for postgres'
    )

    # Connection method 1: RDS Data API
    parser.add_argument('--resource_arn', help='ARN of the RDS cluster (for RDS Data API)')

    # Connection method 2: Psycopg Direct Connection
    parser.add_argument('--hostname', help='Database hostname (for direct PostgreSQL connection)')
    parser.add_argument('--port', type=int, default=5432, help='Database port (default: 5432)')

    # Common parameters
    parser.add_argument(
        '--secret_arn',
        required=True,
        help='ARN of the Secrets Manager secret for database credentials',
    )
    parser.add_argument('--database', required=True, help='Database name')
    parser.add_argument('--region', required=True, help='AWS region')
    parser.add_argument('--readonly', required=True, help='Enforce readonly SQL statements')

    args = parser.parse_args()

    # Validate connection parameters
    if not args.resource_arn and not args.hostname:
        parser.error(
            'Either --resource_arn (for RDS Data API) or '
            '--hostname (for direct PostgreSQL) must be provided'
        )

    if args.resource_arn and args.hostname:
        parser.error(
            'Cannot specify both --resource_arn and --hostname. Choose one connection method.'
        )

    # Convert args to dict for easier handling
    connection_params = vars(args)

    # Convert readonly string to boolean
    connection_params['readonly'] = args.readonly.lower() == 'true'

    # Log connection information
    connection_target = args.resource_arn if args.resource_arn else f'{args.hostname}:{args.port}'

    if args.resource_arn:
        logger.info(
            f'Postgres MCP init with RDS Data API: CONNECTION_TARGET:{connection_target}, SECRET_ARN:{args.secret_arn}, REGION:{args.region}, DATABASE:{args.database}, READONLY:{args.readonly}'
        )
    else:
        logger.info(
            f'Postgres MCP init with psycopg: CONNECTION_TARGET:{connection_target}, PORT:{args.port}, DATABASE:{args.database}, READONLY:{args.readonly}'
        )

    # Create the appropriate database connection based on the provided parameters
    db_connection = None

    try:
        if args.resource_arn:
            # Use RDS Data API with singleton pattern
            try:
                # Initialize the RDS Data API connection singleton
                DBConnectionSingleton.initialize(
                    resource_arn=args.resource_arn,
                    secret_arn=args.secret_arn,
                    database=args.database,
                    region=args.region,
                    readonly=connection_params['readonly'],
                )

                # Get the connection from the singleton
                db_connection = DBConnectionSingleton.get().db_connection
            except Exception as e:
                logger.exception(f'Failed to create RDS Data API connection: {str(e)}')
                sys.exit(1)

        else:
            # Use Direct PostgreSQL connection using psycopg connection pool
            try:
                # Create a direct PostgreSQL connection pool
                db_connection = PsycopgPoolConnection(
                    host=args.hostname,
                    port=args.port,
                    database=args.database,
                    readonly=connection_params['readonly'],
                    secret_arn=args.secret_arn,
                    region=args.region,
                )
                # Store the connection globally for access by MCP tools
                global _global_db_connection
                _global_db_connection = db_connection
            except Exception as e:
                logger.exception(f'Failed to create PostgreSQL connection: {str(e)}')
                sys.exit(1)

    except BotoCoreError as e:
        logger.exception(f'Failed to create database connection: {str(e)}')
        sys.exit(1)

    # Test database connection
    ctx = DummyCtx()
    response = asyncio.run(run_query('SELECT 1', ctx, db_connection))
    if (
        isinstance(response, list)
        and len(response) == 1
        and isinstance(response[0], dict)
        and 'error' in response[0]
    ):
        logger.error('Failed to validate database connection to Postgres. Exit the MCP server')
        sys.exit(1)

    logger.success('Successfully validated database connection to Postgres')

    logger.info('Starting Postgres MCP server')
    
    # Check if we should run in HTTP mode (for ECS deployment)
    import os
    if os.getenv('MCP_HOST') and os.getenv('MCP_PORT'):
        host = os.getenv('MCP_HOST', '0.0.0.0')
        port = int(os.getenv('MCP_PORT', '8000'))
        logger.info(f'Running in HTTP mode on {host}:{port}')
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        logger.info('Running in stdio mode')
        mcp.run()


if __name__ == '__main__':
    main()
