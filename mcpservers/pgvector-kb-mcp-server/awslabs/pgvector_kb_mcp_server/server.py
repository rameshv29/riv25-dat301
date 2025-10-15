# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""PostgreSQL pgvector Knowledge Base MCP Server."""

import json
import os
import sys
import time
from typing import List, Literal, Optional

from loguru import logger
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from .database.connection import db_connection
from .database.operations import kb_operations
from .embeddings.generator import embedding_generator
from .models import DocumentMetadata, KnowledgeBaseDocument

# Remove all default handlers then add our own
logger.remove()
logger.add(sys.stderr, level='INFO')

mcp = FastMCP(
    'awslabs.pgvector-kb-mcp-server',
    instructions="""
    The AWS Labs PostgreSQL pgvector Knowledge Base MCP Server provides access to PostgreSQL maintenance 
    and vacuum documentation stored in a pgvector-enabled database for semantic search and retrieval.

    ## Usage Workflow:
    1. Use the ListDocuments tool to discover available PostgreSQL maintenance documents
    2. Use the QueryKnowledgeBase tool to search documents with natural language queries
    3. Use the GetDocument tool to retrieve full content of specific documents
    4. Use the IngestDocument tool to add new maintenance documents (if needed)

    ## Document Types:
    - PostgreSQL vacuum and maintenance procedures
    - Performance tuning guides
    - Troubleshooting runbooks
    - Best practices documentation

    ## Search Capabilities:
    - Semantic search using vector embeddings
    - Full-text search for exact matches
    - Hybrid search combining both approaches
    - Metadata filtering by document type and tags
    """,
    dependencies=['psycopg', 'pgvector', 'sentence-transformers', 'boto3'],
)


# Add health check endpoint for ALB health checks
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check endpoint for load balancer."""
    try:
        # Test database connection
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('SELECT 1')
                await cur.fetchone()
        return PlainTextResponse("OK")
    except Exception as e:
        logger.error(f'Health check failed: {e}')
        return PlainTextResponse("UNHEALTHY", status_code=503)


@mcp.tool(name='ListDocuments')
async def list_documents_tool(
    document_type: Optional[str] = Field(
        None, 
        description='Filter by document type (e.g., "postgresql_maintenance", "vacuum_guide")'
    ),
    limit: int = Field(20, description='Maximum number of documents to return'),
    offset: int = Field(0, description='Number of documents to skip for pagination')
) -> str:
    """List available PostgreSQL maintenance documents in the knowledge base.

    Returns a list of documents with their metadata, including:
    - id: Unique document identifier
    - title: Document title
    - content: Truncated content preview
    - metadata: Document metadata including tags, source, and type
    - created_at: When the document was added

    ## Example response structure:
    ```json
    {
        "documents": [
            {
                "id": 1,
                "title": "Cost-based Vacuum Delay",
                "content": "During the execution of VACUUM and ANALYZE commands...",
                "metadata": {
                    "document_type": "postgresql_maintenance",
                    "section": "vacuum_tuning",
                    "tags": ["vacuum", "performance", "tuning"]
                }
            }
        ],
        "total_count": 15,
        "limit": 20,
        "offset": 0
    }
    ```
    """
    try:
        documents, total_count = await kb_operations.list_documents(
            document_type=document_type,
            limit=limit,
            offset=offset
        )
        
        result = {
            'documents': [doc.model_dump() for doc in documents],
            'total_count': total_count,
            'limit': limit,
            'offset': offset
        }
        
        return json.dumps(result, default=str)
        
    except Exception as e:
        logger.error(f'Error listing documents: {e}')
        return json.dumps({'error': str(e)})


@mcp.tool(name='QueryKnowledgeBase')
async def query_knowledge_base_tool(
    query: str = Field(..., description='Natural language query to search the knowledge base'),
    search_type: Literal['semantic', 'text', 'hybrid'] = Field(
        'hybrid', 
        description='Type of search: semantic (vector), text (full-text), or hybrid (both)'
    ),
    limit: int = Field(5, description='Maximum number of results to return'),
    document_type: Optional[str] = Field(
        None, 
        description='Filter by document type (e.g., "postgresql_maintenance")'
    ),
    similarity_threshold: float = Field(
        0.7, 
        description='Minimum similarity score for semantic search (0.0 to 1.0)'
    )
) -> str:
    """Query the PostgreSQL maintenance knowledge base using natural language.

    ## Search Types:
    - **semantic**: Uses vector embeddings to find conceptually similar content
    - **text**: Uses full-text search for exact keyword matches
    - **hybrid**: Combines both semantic and text search for best results

    ## Query Examples:
    - "How to tune vacuum cost delay parameters?"
    - "What causes vacuum to run slowly?"
    - "Best practices for autovacuum configuration"
    - "Troubleshooting vacuum blocking issues"

    ## Response Format:
    Returns JSON with matching documents, each containing:
    - content: The relevant text content
    - title: Document title
    - similarity_score: Relevance score (higher is better)
    - metadata: Document metadata and source information

    ## Usage Tips:
    - Use specific PostgreSQL terms for better results
    - Try different search types if initial results aren't relevant
    - Lower similarity_threshold to get more results
    - Use document_type filter to narrow search scope
    """
    try:
        start_time = time.time()
        
        # Generate query embedding for semantic/hybrid search
        query_embedding = None
        if search_type in ['semantic', 'hybrid']:
            query_embedding = await embedding_generator.generate_embedding(query)
        
        # Perform search based on type
        if search_type == 'semantic':
            documents = await kb_operations.semantic_search(
                query_embedding=query_embedding,
                limit=limit,
                similarity_threshold=similarity_threshold,
                document_type=document_type
            )
        elif search_type == 'text':
            documents = await kb_operations.text_search(
                query=query,
                limit=limit,
                document_type=document_type
            )
        else:  # hybrid
            documents = await kb_operations.hybrid_search(
                query=query,
                query_embedding=query_embedding,
                limit=limit,
                document_type=document_type
            )
        
        execution_time = (time.time() - start_time) * 1000
        
        result = {
            'query': query,
            'search_type': search_type,
            'documents': [doc.model_dump() for doc in documents],
            'total_results': len(documents),
            'execution_time_ms': round(execution_time, 2)
        }
        
        return json.dumps(result, default=str)
        
    except Exception as e:
        logger.error(f'Error querying knowledge base: {e}')
        return json.dumps({'error': str(e), 'query': query})


@mcp.tool(name='GetDocument')
async def get_document_tool(
    document_id: int = Field(..., description='Unique identifier of the document to retrieve')
) -> str:
    """Retrieve the full content of a specific document by its ID.

    Use this tool when you need the complete content of a document that was found 
    through ListDocuments or QueryKnowledgeBase tools.

    ## Response Format:
    Returns the complete document with:
    - id: Document identifier
    - title: Full document title
    - content: Complete document content
    - metadata: All document metadata
    - source information and timestamps
    """
    try:
        document = await kb_operations.get_document_by_id(document_id)
        
        if not document:
            return json.dumps({'error': f'Document with ID {document_id} not found'})
        
        return json.dumps(document.model_dump(), default=str)
        
    except Exception as e:
        logger.error(f'Error retrieving document {document_id}: {e}')
        return json.dumps({'error': str(e), 'document_id': document_id})


@mcp.tool(name='IngestDocument')
async def ingest_document_tool(
    title: str = Field(..., description='Title of the document'),
    content: str = Field(..., description='Full content of the document'),
    document_type: str = Field('postgresql_maintenance', description='Type of document'),
    source_url: Optional[str] = Field(None, description='Source URL of the document'),
    tags: List[str] = Field(default_factory=list, description='Tags for categorizing the document'),
    section: Optional[str] = Field(None, description='Section or category within the document type')
) -> str:
    """Ingest a new document into the knowledge base.

    This tool allows adding new PostgreSQL maintenance documents to the knowledge base.
    The document will be automatically processed to generate embeddings for semantic search.

    ## Parameters:
    - **title**: Clear, descriptive title for the document
    - **content**: Full text content of the document
    - **document_type**: Category (default: "postgresql_maintenance")
    - **source_url**: Optional URL where the document originated
    - **tags**: List of tags for categorization (e.g., ["vacuum", "performance"])
    - **section**: Optional section within the document type

    ## Response:
    Returns the ID of the newly created document and ingestion status.
    """
    try:
        # Generate embedding for the content
        embedding = await embedding_generator.generate_embedding(content)
        
        # Create metadata
        metadata = DocumentMetadata(
            document_type=document_type,
            source_url=source_url,
            tags=tags,
            section=section
        )
        
        # Ingest the document
        document_id = await kb_operations.ingest_document(
            title=title,
            content=content,
            embedding=embedding,
            metadata=metadata
        )
        
        result = {
            'document_id': document_id,
            'title': title,
            'status': 'success',
            'message': f'Document successfully ingested with ID {document_id}'
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f'Error ingesting document: {e}')
        return json.dumps({
            'status': 'error',
            'message': str(e),
            'title': title
        })


async def startup_handler():
    """Initialize database and embedding generator on startup."""
    try:
        await db_connection.initialize()
        await embedding_generator.initialize()
        logger.info('pgvector Knowledge Base MCP Server initialized successfully')
    except Exception as e:
        logger.error(f'Failed to initialize server: {e}')
        raise


def main():
    """Run the MCP server with CLI argument support."""
    # Initialize on startup
    import asyncio
    asyncio.run(startup_handler())
    
    # Check if we should run in HTTP mode (for ECS deployment)
    if os.getenv('MCP_HOST') and os.getenv('MCP_PORT'):
        host = os.getenv('MCP_HOST', '0.0.0.0')
        port = int(os.getenv('MCP_PORT', '8000'))
        logger.info(f'Running pgvector KB MCP server in HTTP mode on {host}:{port}')
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        logger.info('Running pgvector KB MCP server in stdio mode')
        mcp.run()


if __name__ == '__main__':
    main()