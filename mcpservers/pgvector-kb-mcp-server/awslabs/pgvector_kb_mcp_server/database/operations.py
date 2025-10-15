# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Database operations for pgvector knowledge base."""

import json
import time
from typing import List, Optional, Tuple
import numpy as np
from psycopg import sql
from loguru import logger

from ..models import KnowledgeBaseDocument, DocumentMetadata, QueryResult
from .connection import db_connection


class KnowledgeBaseOperations:
    """Database operations for the knowledge base."""
    
    async def ingest_document(
        self, 
        title: str, 
        content: str, 
        embedding: np.ndarray,
        metadata: DocumentMetadata
    ) -> int:
        """Ingest a document into the knowledge base."""
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                    INSERT INTO kb_documents 
                    (title, content, content_embedding, metadata, source_url, document_type)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (
                    title,
                    content,
                    embedding.tolist(),
                    json.dumps(metadata.model_dump()),
                    metadata.source_url,
                    metadata.document_type
                ))
                
                result = await cur.fetchone()
                document_id = result[0] if result else None
                
                await conn.commit()
                logger.info(f'Document ingested with ID: {document_id}')
                return document_id
    
    async def semantic_search(
        self,
        query_embedding: np.ndarray,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        document_type: Optional[str] = None
    ) -> List[KnowledgeBaseDocument]:
        """Perform semantic search using vector similarity."""
        start_time = time.time()
        
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cur:
                # Build query with optional document type filter
                base_query = '''
                    SELECT 
                        id, title, content, metadata, source_url, document_type,
                        created_at, updated_at,
                        1 - (content_embedding <=> %s) as similarity_score
                    FROM kb_documents
                    WHERE content_embedding IS NOT NULL
                '''
                
                params = [query_embedding.tolist()]
                
                if document_type:
                    base_query += ' AND document_type = %s'
                    params.append(document_type)
                
                base_query += '''
                    AND (1 - (content_embedding <=> %s)) >= %s
                    ORDER BY content_embedding <=> %s
                    LIMIT %s
                '''
                
                params.extend([query_embedding.tolist(), similarity_threshold, query_embedding.tolist(), limit])
                
                await cur.execute(base_query, params)
                rows = await cur.fetchall()
                
                documents = []
                for row in rows:
                    metadata_dict = row[3] if row[3] else {}
                    metadata = DocumentMetadata(**metadata_dict)
                    
                    doc = KnowledgeBaseDocument(
                        id=row[0],
                        title=row[1],
                        content=row[2],
                        metadata=metadata,
                        similarity_score=float(row[8])
                    )
                    documents.append(doc)
                
                execution_time = (time.time() - start_time) * 1000
                logger.info(f'Semantic search completed in {execution_time:.2f}ms, found {len(documents)} documents')
                
                return documents
    
    async def text_search(
        self,
        query: str,
        limit: int = 10,
        document_type: Optional[str] = None
    ) -> List[KnowledgeBaseDocument]:
        """Perform full-text search."""
        start_time = time.time()
        
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cur:
                base_query = '''
                    SELECT 
                        id, title, content, metadata, source_url, document_type,
                        created_at, updated_at,
                        ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s)) as rank
                    FROM kb_documents
                    WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                '''
                
                params = [query, query]
                
                if document_type:
                    base_query += ' AND document_type = %s'
                    params.append(document_type)
                
                base_query += '''
                    ORDER BY rank DESC
                    LIMIT %s
                '''
                params.append(limit)
                
                await cur.execute(base_query, params)
                rows = await cur.fetchall()
                
                documents = []
                for row in rows:
                    metadata_dict = row[3] if row[3] else {}
                    metadata = DocumentMetadata(**metadata_dict)
                    
                    doc = KnowledgeBaseDocument(
                        id=row[0],
                        title=row[1],
                        content=row[2],
                        metadata=metadata,
                        similarity_score=float(row[8])  # Using rank as similarity score
                    )
                    documents.append(doc)
                
                execution_time = (time.time() - start_time) * 1000
                logger.info(f'Text search completed in {execution_time:.2f}ms, found {len(documents)} documents')
                
                return documents
    
    async def hybrid_search(
        self,
        query: str,
        query_embedding: np.ndarray,
        limit: int = 10,
        semantic_weight: float = 0.7,
        text_weight: float = 0.3,
        document_type: Optional[str] = None
    ) -> List[KnowledgeBaseDocument]:
        """Perform hybrid search combining semantic and text search."""
        # Get results from both search methods
        semantic_results = await self.semantic_search(
            query_embedding, limit * 2, document_type=document_type
        )
        text_results = await self.text_search(query, limit * 2, document_type=document_type)
        
        # Combine and re-rank results
        combined_docs = {}
        
        # Add semantic results
        for doc in semantic_results:
            combined_docs[doc.id] = doc
            doc.similarity_score = doc.similarity_score * semantic_weight
        
        # Add text results and combine scores
        for doc in text_results:
            if doc.id in combined_docs:
                combined_docs[doc.id].similarity_score += doc.similarity_score * text_weight
            else:
                doc.similarity_score = doc.similarity_score * text_weight
                combined_docs[doc.id] = doc
        
        # Sort by combined score and return top results
        sorted_docs = sorted(
            combined_docs.values(), 
            key=lambda x: x.similarity_score, 
            reverse=True
        )
        
        return sorted_docs[:limit]
    
    async def list_documents(
        self,
        document_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[KnowledgeBaseDocument], int]:
        """List documents in the knowledge base."""
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cur:
                # Count total documents
                count_query = 'SELECT COUNT(*) FROM kb_documents'
                count_params = []
                
                if document_type:
                    count_query += ' WHERE document_type = %s'
                    count_params.append(document_type)
                
                await cur.execute(count_query, count_params)
                total_count = (await cur.fetchone())[0]
                
                # Get documents
                base_query = '''
                    SELECT 
                        id, title, content, metadata, source_url, document_type,
                        created_at, updated_at
                    FROM kb_documents
                '''
                
                params = []
                if document_type:
                    base_query += ' WHERE document_type = %s'
                    params.append(document_type)
                
                base_query += '''
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                '''
                params.extend([limit, offset])
                
                await cur.execute(base_query, params)
                rows = await cur.fetchall()
                
                documents = []
                for row in rows:
                    metadata_dict = row[3] if row[3] else {}
                    metadata = DocumentMetadata(**metadata_dict)
                    
                    doc = KnowledgeBaseDocument(
                        id=row[0],
                        title=row[1],
                        content=row[2][:500] + '...' if len(row[2]) > 500 else row[2],  # Truncate for listing
                        metadata=metadata
                    )
                    documents.append(doc)
                
                return documents, total_count
    
    async def get_document_by_id(self, document_id: int) -> Optional[KnowledgeBaseDocument]:
        """Get a specific document by ID."""
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                    SELECT 
                        id, title, content, metadata, source_url, document_type,
                        created_at, updated_at
                    FROM kb_documents
                    WHERE id = %s
                ''', (document_id,))
                
                row = await cur.fetchone()
                if not row:
                    return None
                
                metadata_dict = row[3] if row[3] else {}
                metadata = DocumentMetadata(**metadata_dict)
                
                return KnowledgeBaseDocument(
                    id=row[0],
                    title=row[1],
                    content=row[2],
                    metadata=metadata
                )


# Global operations instance
kb_operations = KnowledgeBaseOperations()