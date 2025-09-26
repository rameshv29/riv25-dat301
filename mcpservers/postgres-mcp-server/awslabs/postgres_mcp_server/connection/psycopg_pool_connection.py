# Fixed version of psycopg_pool_connection.py
# Key changes:
# 1. Don't open the pool in the constructor
# 2. Properly manage async pool lifecycle
# 3. Use lazy initialization

import boto3
import json
from awslabs.postgres_mcp_server.connection.abstract_db_connection import AbstractDBConnection
from loguru import logger
from psycopg_pool import AsyncConnectionPool
from typing import Any, Dict, List, Optional, Tuple


class PsycopgPoolConnection(AbstractDBConnection):
    """Fixed class that wraps DB connection using psycopg connection pool."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        readonly: bool,
        secret_arn: str,
        region: str,
        min_size: int = 1,
        max_size: int = 10,
        is_test: bool = False,
    ):
        """Initialize a new DB connection pool."""
        super().__init__(readonly)
        self.host = host
        self.port = port
        self.database = database
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional['AsyncConnectionPool[Any]'] = None
        self._pool_initialized = False

        # Get credentials from Secrets Manager
        logger.info(f'Retrieving credentials from Secrets Manager: {secret_arn}')
        self.user, self.password = self._get_credentials_from_secret(secret_arn, region, is_test)
        logger.info(f'Successfully retrieved credentials for user: {self.user}')

        # Store connection info
        if not is_test:
            self.conninfo = f'host={host} port={port} dbname={database} user={self.user} password={self.password}'
            logger.info('Connection parameters stored')

    async def initialize_pool(self):
        """Initialize the connection pool - FIXED VERSION."""
        if self.pool is None and not self._pool_initialized:
            logger.info(
                f'Initializing connection pool with min_size={self.min_size}, max_size={self.max_size}'
            )
            
            # ✅ FIX: Create pool with open=False, then open it properly in async context
            self.pool = AsyncConnectionPool(
                self.conninfo, 
                min_size=self.min_size, 
                max_size=self.max_size, 
                open=False  # ✅ KEY FIX: Don't open in constructor
            )
            
            # ✅ FIX: Open the pool in proper async context
            await self.pool.open()
            self._pool_initialized = True
            
            logger.info('Connection pool initialized successfully')

            # Set read-only mode if needed
            if self.readonly_query:
                await self._set_all_connections_readonly()

    async def _get_connection(self):
        """Get a database connection from the pool - FIXED VERSION."""
        # ✅ FIX: Always ensure pool is initialized before use
        if not self._pool_initialized:
            await self.initialize_pool()

        if self.pool is None:
            raise ValueError('Failed to initialize connection pool')

        return self.pool.connection(timeout=15.0)

    async def execute_query(
        self, sql: str, parameters: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Execute a SQL query using async connection - FIXED VERSION."""
        try:
            # ✅ FIX: Ensure pool is ready before executing queries
            if not self._pool_initialized:
                await self.initialize_pool()
                
            async with await self._get_connection() as conn:
                async with conn.transaction():
                    if self.readonly_query:
                        await conn.execute('SET TRANSACTION READ ONLY')

                    # Create a cursor for better control
                    async with conn.cursor() as cursor:
                        # Execute the query
                        if parameters:
                            params = self._convert_parameters(parameters)
                            # ✅ FIX: Convert RDS Data API parameter syntax to psycopg syntax
                            converted_sql, converted_params = self._convert_named_parameters_to_psycopg(sql, params)
                            await cursor.execute(converted_sql, converted_params)
                        else:
                            await cursor.execute(sql)

                        # Check if there are results to fetch
                        if cursor.description:
                            # Get column names
                            columns = [desc[0] for desc in cursor.description]

                            # Fetch all rows
                            rows = await cursor.fetchall()

                            # Structure the response
                            column_metadata = [{'name': col} for col in columns]
                            records = []

                            # Convert each row to the expected format
                            for row in rows:
                                record = []
                                for value in row:
                                    if value is None:
                                        record.append({'isNull': True})
                                    elif isinstance(value, str):
                                        record.append({'stringValue': value})
                                    elif isinstance(value, int):
                                        record.append({'longValue': value})
                                    elif isinstance(value, float):
                                        record.append({'doubleValue': value})
                                    elif isinstance(value, bool):
                                        record.append({'booleanValue': value})
                                    elif isinstance(value, bytes):
                                        record.append({'blobValue': value})
                                    else:
                                        # Convert other types to string
                                        record.append({'stringValue': str(value)})
                                records.append(record)

                            return {'columnMetadata': column_metadata, 'records': records}
                        else:
                            # No results (e.g., for INSERT, UPDATE, etc.)
                            return {'columnMetadata': [], 'records': []}

        except Exception as e:
            logger.error(f'Database connection error: {str(e)}')
            raise e

    async def _set_all_connections_readonly(self):
        """Set all connections in the pool to read-only mode."""
        if self.pool is None:
            logger.warning('Connection pool is not initialized, cannot set read-only mode')
            return

        try:
            async with self.pool.connection(timeout=15.0) as conn:
                await conn.execute(
                    'ALTER ROLE CURRENT_USER SET default_transaction_read_only = on'
                )
                logger.info('Successfully set connection to read-only mode')
        except Exception as e:
            logger.warning(f'Failed to set connections to read-only mode: {str(e)}')
            logger.warning('Continuing without setting read-only mode')

    def _convert_parameters(self, parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transform structured parameter format to psycopg's native parameter format."""
        result = {}
        for param in parameters:
            name = param.get('name')
            value = param.get('value', {})

            # Extract the value based on its type
            if 'stringValue' in value:
                result[name] = value['stringValue']
            elif 'longValue' in value:
                result[name] = value['longValue']
            elif 'doubleValue' in value:
                result[name] = value['doubleValue']
            elif 'booleanValue' in value:
                result[name] = value['booleanValue']
            elif 'blobValue' in value:
                result[name] = value['blobValue']
            elif 'isNull' in value and value['isNull']:
                result[name] = None

        return result

    def _convert_named_parameters_to_psycopg(self, sql: str, parameters: dict) -> tuple:
        """
        Convert named parameters from RDS Data API format to psycopg format
        
        RDS Data API uses: SELECT * FROM table WHERE id = :id
        psycopg uses: SELECT * FROM table WHERE id = %(id)s
        """
        import re
        
        # Convert :param_name to %(param_name)s
        converted_sql = sql
        for param_name in parameters.keys():
            # Replace :param_name with %(param_name)s
            pattern = f':{param_name}\\b'  # Word boundary to avoid partial matches
            replacement = f'%({param_name})s'
            converted_sql = re.sub(pattern, replacement, converted_sql)
        
        return converted_sql, parameters

    def _get_credentials_from_secret(
        self, secret_arn: str, region: str, is_test: bool = False
    ) -> Tuple[str, str]:
        """Get database credentials from AWS Secrets Manager."""
        if is_test:
            return 'test_user', 'test_password'

        try:
            # Create a Secrets Manager client
            logger.info(f'Creating Secrets Manager client in region {region}')
            session = boto3.Session()
            client = session.client(service_name='secretsmanager', region_name=region)

            # Get the secret value
            logger.info(f'Retrieving secret value for {secret_arn}')
            get_secret_value_response = client.get_secret_value(SecretId=secret_arn)
            logger.info('Successfully retrieved secret value')

            # Parse the secret string
            if 'SecretString' in get_secret_value_response:
                secret = json.loads(get_secret_value_response['SecretString'])
                logger.info(f'Secret keys: {", ".join(secret.keys())}')

                # Extract username and password
                username = secret.get('username') or secret.get('user') or secret.get('Username')
                password = secret.get('password') or secret.get('Password')

                if not username:
                    logger.error(
                        f'Username not found in secret. Available keys: {", ".join(secret.keys())}'
                    )
                    raise ValueError(
                        f'Secret does not contain username. Available keys: {", ".join(secret.keys())}'
                    )

                if not password:
                    logger.error('Password not found in secret')
                    raise ValueError(
                        f'Secret does not contain password. Available keys: {", ".join(secret.keys())}'
                    )

                logger.info(f'Successfully extracted credentials for user: {username}')
                return username, password
            else:
                logger.error('Secret does not contain a SecretString')
                raise ValueError('Secret does not contain a SecretString')
        except Exception as e:
            logger.error(f'Error retrieving secret: {str(e)}')
            raise ValueError(f'Failed to retrieve credentials from Secrets Manager: {str(e)}')

    async def close(self) -> None:
        """Close all connections in the pool - FIXED VERSION."""
        if self.pool is not None:
            logger.info('Closing connection pool')
            await self.pool.close()
            self.pool = None
            self._pool_initialized = False  # ✅ FIX: Reset initialization flag
            logger.info('Connection pool closed successfully')

    async def check_connection_health(self) -> bool:
        """Check if the connection is healthy."""
        try:
            result = await self.execute_query('SELECT 1')
            return len(result.get('records', [])) > 0
        except Exception as e:
            logger.error(f'Connection health check failed: {str(e)}')
            return False

    def get_pool_stats(self) -> Dict[str, int]:
        """Get current connection pool statistics."""
        if not hasattr(self, 'pool') or self.pool is None:
            return {'size': 0, 'min_size': self.min_size, 'max_size': self.max_size, 'idle': 0}

        # Access pool attributes safely
        size = getattr(self.pool, 'size', 0)
        min_size = getattr(self.pool, 'min_size', self.min_size)
        max_size = getattr(self.pool, 'max_size', self.max_size)
        idle = getattr(self.pool, 'idle', 0)

        return {'size': size, 'min_size': min_size, 'max_size': max_size, 'idle': idle}