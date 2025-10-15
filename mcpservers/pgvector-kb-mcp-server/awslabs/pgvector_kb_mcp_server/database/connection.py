# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Database connection management for pgvector knowledge base."""

import json
import os
from typing import Optional
import boto3
import psycopg
from psycopg import sql
from psycopg.pool import ConnectionPool
from loguru import logger


class DatabaseConnection:
    """Manages PostgreSQL database connections with pgvector support."""
    
    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._connection_string: Optional[str] = None
        
    async def initialize(self) -> None:
        """Initialize the database connection pool."""
        if self._pool is not None:
            return
            
        connection_string = await self._get_connection_string()
        
        # Create connection pool
        self._pool = ConnectionPool(
            connection_string,
            min_size=2,
            max_size=10,
            open=True
        )
        
        # Initialize database schema
        await self._initialize_schema()
        logger.info('Database connection pool initialized')
    
    async def _get_connection_string(self) -> str:
        """Get database connection string from environment or AWS Secrets Manager."""
        if self._connection_string:
            return self._connection_string
            
        # Try environment variables first
        host = os.getenv('POSTGRES_HOST')
        port = os.getenv('POSTGRES_PORT', '5432')
        database = os.getenv('POSTGRES_DB', 'workshop_db')
        user = os.getenv('POSTGRES_USER', 'workshop_admin')
        password = os.getenv('POSTGRES_PASSWORD')
        
        # If password not in env, try AWS Secrets Manager
        if not password:
            secret_arn = os.getenv('POSTGRES_PASSWORD_SECRET_ARN')
            if secret_arn:
                password = await self._get_secret_value(secret_arn)
        
        if not all([host, user, password]):
            raise ValueError('Missing required database connection parameters')
        
        self._connection_string = f'postgresql://{user}:{password}@{host}:{port}/{database}'
        return self._connection_string
    
    async def _get_secret_value(self, secret_arn: str) -> str:
        """Retrieve password from AWS Secrets Manager."""
        try:
            session = boto3.Session()
            client = session.client('secretsmanager')
            response = client.get_secret_value(SecretId=secret_arn)
            
            if 'SecretString' in response:
                secret = json.loads(response['SecretString'])
                return secret.get('password', '')
            else:
                raise ValueError('Secret does not contain SecretString')
                
        except Exception as e:
            logger.error(f'Failed to retrieve secret: {e}')
            raise
    
    async def _initialize_schema(self) -> None:
        """Initialize database schema with pgvector extension and tables."""
        if not self._pool:
            raise RuntimeError('Database pool not initialized')
            
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                # Enable pgvector extension
                await cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
                
                # Create documents table
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS kb_documents (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(255) NOT NULL,
                        content TEXT NOT NULL,
                        content_embedding vector(384),  -- sentence-transformers embedding size
                        metadata JSONB DEFAULT '{}',
                        source_url TEXT,
                        document_type VARCHAR(50) DEFAULT 'postgresql_maintenance',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create vector similarity index
                await cur.execute('''
                    CREATE INDEX IF NOT EXISTS kb_documents_embedding_idx 
                    ON kb_documents USING ivfflat (content_embedding vector_cosine_ops)
                    WITH (lists = 100)
                ''')
                
                # Create text search index
                await cur.execute('''
                    CREATE INDEX IF NOT EXISTS kb_documents_content_idx 
                    ON kb_documents USING gin(to_tsvector('english', content))
                ''')
                
                # Create metadata index
                await cur.execute('''
                    CREATE INDEX IF NOT EXISTS kb_documents_metadata_idx 
                    ON kb_documents USING gin(metadata)
                ''')
                
                await conn.commit()
                logger.info('Database schema initialized successfully')
    
    async def get_connection(self):
        """Get a database connection from the pool."""
        if not self._pool:
            await self.initialize()
        return self._pool.connection()
    
    async def close(self) -> None:
        """Close the database connection pool."""
        if self._pool:
            self._pool.close()
            self._pool = None
            logger.info('Database connection pool closed')


# Global database connection instance
db_connection = DatabaseConnection()