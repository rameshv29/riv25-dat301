# PostgreSQL pgvector Knowledge Base MCP Server

MCP server for storing and retrieving PostgreSQL maintenance documentation using pgvector for semantic search.

## Features

### Document Storage and Retrieval
- Store PostgreSQL maintenance documents in Aurora PostgreSQL with pgvector
- Semantic search using vector embeddings
- Full-text search for exact keyword matches
- Hybrid search combining both approaches

### PostgreSQL Maintenance Focus
- Vacuum and autovacuum documentation
- Performance tuning guides
- Troubleshooting runbooks
- Best practices documentation

### Advanced Search Capabilities
- Vector similarity search using pgvector
- Full-text search with PostgreSQL's built-in capabilities
- Metadata filtering by document type and tags
- Configurable similarity thresholds

## Prerequisites

### Database Requirements
1. **Aurora PostgreSQL**: Cluster with pgvector extension enabled
2. **Database Setup**: The server automatically creates required tables and indexes
3. **Connection**: Database connection via environment variables or AWS Secrets Manager

### Environment Variables

```bash
# Database connection
POSTGRES_HOST=your-aurora-cluster-endpoint
POSTGRES_PORT=5432
POSTGRES_DB=workshop_db
POSTGRES_USER=workshop_admin
POSTGRES_PASSWORD=your-password
# OR use AWS Secrets Manager
POSTGRES_PASSWORD_SECRET_ARN=arn:aws:secretsmanager:region:account:secret:name

# Embedding model configuration
EMBEDDING_MODEL=sentence-transformers  # or amazon.titan-embed-text-v1
SENTENCE_TRANSFORMER_MODEL=all-MiniLM-L6-v2  # if using sentence-transformers
AWS_REGION=us-west-2  # if using Bedrock embeddings

# MCP Server configuration
MCP_HOST=0.0.0.0  # for HTTP mode
MCP_PORT=8000     # for HTTP mode
```

## Installation

### Local Development

```bash
# Install dependencies
uv sync

# Run the server
uv run python -m awslabs.pgvector_kb_mcp_server.server
```

### Docker Deployment

```bash
# Build the image
docker build -t pgvector-kb-mcp-server .

# Run the container
docker run -p 8000:8000 \
  -e POSTGRES_HOST=your-host \
  -e POSTGRES_USER=your-user \
  -e POSTGRES_PASSWORD=your-password \
  pgvector-kb-mcp-server
```

### MCP Client Configuration

```json
{
  "mcpServers": {
    "pgvector-kb": {
      "command": "uvx",
      "args": ["awslabs.pgvector-kb-mcp-server@latest"],
      "env": {
        "POSTGRES_HOST": "your-aurora-endpoint",
        "POSTGRES_USER": "workshop_admin",
        "POSTGRES_PASSWORD": "your-password",
        "EMBEDDING_MODEL": "sentence-transformers"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## Available Tools

### ListDocuments
List available PostgreSQL maintenance documents with metadata and content previews.

**Parameters:**
- `document_type` (optional): Filter by document type
- `limit`: Maximum number of documents to return (default: 20)
- `offset`: Number of documents to skip for pagination (default: 0)

### QueryKnowledgeBase
Search documents using natural language queries with multiple search strategies.

**Parameters:**
- `query`: Natural language search query
- `search_type`: "semantic", "text", or "hybrid" (default: "hybrid")
- `limit`: Maximum number of results (default: 5)
- `document_type` (optional): Filter by document type
- `similarity_threshold`: Minimum similarity score for semantic search (default: 0.7)

### GetDocument
Retrieve the complete content of a specific document by ID.

**Parameters:**
- `document_id`: Unique identifier of the document

### IngestDocument
Add new PostgreSQL maintenance documents to the knowledge base.

**Parameters:**
- `title`: Document title
- `content`: Full document content
- `document_type`: Type of document (default: "postgresql_maintenance")
- `source_url` (optional): Source URL
- `tags`: List of tags for categorization
- `section` (optional): Section within document type

## Database Schema

The server automatically creates the following schema:

```sql
-- Main documents table
CREATE TABLE kb_documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    content_embedding vector(384),  -- Configurable dimension
    metadata JSONB DEFAULT '{}',
    source_url TEXT,
    document_type VARCHAR(50) DEFAULT 'postgresql_maintenance',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX kb_documents_embedding_idx ON kb_documents 
    USING ivfflat (content_embedding vector_cosine_ops);
CREATE INDEX kb_documents_content_idx ON kb_documents 
    USING gin(to_tsvector('english', content));
CREATE INDEX kb_documents_metadata_idx ON kb_documents 
    USING gin(metadata);
```

## Example Usage

### Search for Vacuum Information
```python
# Query for vacuum tuning information
result = await query_knowledge_base_tool(
    query="How to configure vacuum cost delay for better performance?",
    search_type="hybrid",
    limit=3
)
```

### List All Documents
```python
# Get all PostgreSQL maintenance documents
documents = await list_documents_tool(
    document_type="postgresql_maintenance",
    limit=10
)
```

### Add New Document
```python
# Ingest a new maintenance document
result = await ingest_document_tool(
    title="Advanced Vacuum Troubleshooting",
    content="When vacuum operations are slow or blocked...",
    tags=["vacuum", "troubleshooting", "performance"],
    section="troubleshooting"
)
```

## Architecture

The server consists of several key components:

- **Database Layer**: PostgreSQL connection management with pgvector support
- **Embedding Layer**: Text embedding generation using sentence-transformers or Bedrock
- **Search Layer**: Semantic, text, and hybrid search implementations
- **MCP Layer**: FastMCP server with tool definitions and HTTP endpoints

## Performance Considerations

- **Vector Index**: Uses IVFFlat index for fast similarity search
- **Connection Pooling**: Maintains connection pool for database efficiency
- **Embedding Caching**: Consider implementing embedding caching for frequently queried content
- **Batch Processing**: Support for batch document ingestion

## Monitoring

The server includes:
- Health check endpoint at `/health`
- Structured logging with loguru
- Performance metrics for search operations
- Database connection monitoring

## Limitations

- Embedding dimension is fixed per deployment (default: 384 for sentence-transformers)
- Vector index performance depends on data size and configuration
- Sentence transformer models require CPU/memory resources
- Bedrock embeddings require AWS credentials and API limits apply