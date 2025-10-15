# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for pgvector knowledge base MCP server."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata for a knowledge base document."""
    
    source_url: Optional[str] = None
    document_type: str = 'postgresql_maintenance'
    section: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class KnowledgeBaseDocument(BaseModel):
    """A document in the knowledge base."""
    
    id: Optional[int] = None
    title: str
    content: str
    metadata: DocumentMetadata
    similarity_score: Optional[float] = None


class QueryResult(BaseModel):
    """Result from a knowledge base query."""
    
    documents: List[KnowledgeBaseDocument]
    total_results: int
    query: str
    execution_time_ms: float


class DocumentIngestionRequest(BaseModel):
    """Request to ingest a document into the knowledge base."""
    
    title: str
    content: str
    metadata: DocumentMetadata


class DocumentIngestionResponse(BaseModel):
    """Response from document ingestion."""
    
    document_id: int
    title: str
    status: str = 'success'
    message: Optional[str] = None