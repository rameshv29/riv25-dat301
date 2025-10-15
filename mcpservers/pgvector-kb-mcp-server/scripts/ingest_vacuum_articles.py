#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Script to ingest PostgreSQL vacuum articles into the pgvector knowledge base."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from awslabs.pgvector_kb_mcp_server.database.connection import db_connection
from awslabs.pgvector_kb_mcp_server.database.operations import kb_operations
from awslabs.pgvector_kb_mcp_server.embeddings.generator import embedding_generator
from awslabs.pgvector_kb_mcp_server.models import DocumentMetadata


class VacuumArticleIngester:
    """Ingests PostgreSQL vacuum articles into the knowledge base."""
    
    def __init__(self, articles_dir: str):
        self.articles_dir = Path(articles_dir)
        self.document_metadata = {
            'cost_based_vacuum_delay.md': {
                'title': 'Cost-based Vacuum Delay',
                'section': 'vacuum_tuning',
                'tags': ['vacuum', 'performance', 'tuning', 'cost-delay'],
                'description': 'Configuration and tuning of vacuum cost-based delay parameters'
            },
            'routine_vacuuming.md': {
                'title': 'Routine Vacuuming',
                'section': 'vacuum_basics',
                'tags': ['vacuum', 'maintenance', 'autovacuum', 'basics'],
                'description': 'Fundamentals of PostgreSQL vacuum operations and maintenance'
            },
            'vacuum_phases.md': {
                'title': 'VACUUM Progress Reporting',
                'section': 'vacuum_monitoring',
                'tags': ['vacuum', 'monitoring', 'progress', 'phases'],
                'description': 'Understanding vacuum phases and progress reporting'
            }
        }
    
    async def ingest_all_articles(self) -> Dict[str, int]:
        """Ingest all vacuum articles from the directory."""
        results = {}
        
        # Initialize components
        await db_connection.initialize()
        await embedding_generator.initialize()
        
        print("Starting ingestion of PostgreSQL vacuum articles...")
        
        for filename, metadata in self.document_metadata.items():
            file_path = self.articles_dir / filename
            
            if not file_path.exists():
                print(f"Warning: File {filename} not found at {file_path}")
                continue
            
            try:
                document_id = await self.ingest_article(file_path, metadata)
                results[filename] = document_id
                print(f"✓ Ingested {filename} with ID {document_id}")
                
            except Exception as e:
                print(f"✗ Failed to ingest {filename}: {e}")
                results[filename] = None
        
        return results
    
    async def ingest_article(self, file_path: Path, metadata: Dict) -> int:
        """Ingest a single article file."""
        # Read the content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not content.strip():
            raise ValueError(f"File {file_path} is empty")
        
        # Generate embedding
        print(f"Generating embedding for {file_path.name}...")
        embedding = await embedding_generator.generate_embedding(content)
        
        # Create metadata object
        doc_metadata = DocumentMetadata(
            document_type='postgresql_maintenance',
            section=metadata['section'],
            tags=metadata['tags'],
            source_url=f'https://raw.githubusercontent.com/rameshv29/riv25-dat301/main/kb_vacuum_articles/{file_path.name}'
        )
        
        # Ingest the document
        document_id = await kb_operations.ingest_document(
            title=metadata['title'],
            content=content,
            embedding=embedding,
            metadata=doc_metadata
        )
        
        return document_id
    
    async def verify_ingestion(self, results: Dict[str, int]) -> None:
        """Verify that documents were ingested correctly."""
        print("\nVerifying ingestion...")
        
        for filename, document_id in results.items():
            if document_id is None:
                continue
                
            try:
                doc = await kb_operations.get_document_by_id(document_id)
                if doc:
                    print(f"✓ {filename}: Document ID {document_id} verified")
                    print(f"  Title: {doc.title}")
                    print(f"  Content length: {len(doc.content)} characters")
                    print(f"  Tags: {doc.metadata.tags}")
                else:
                    print(f"✗ {filename}: Document ID {document_id} not found")
                    
            except Exception as e:
                print(f"✗ {filename}: Verification failed: {e}")
    
    async def test_search(self) -> None:
        """Test search functionality with sample queries."""
        print("\nTesting search functionality...")
        
        test_queries = [
            "vacuum cost delay configuration",
            "autovacuum tuning parameters",
            "vacuum progress monitoring"
        ]
        
        for query in test_queries:
            try:
                # Generate query embedding
                query_embedding = await embedding_generator.generate_embedding(query)
                
                # Perform semantic search
                results = await kb_operations.semantic_search(
                    query_embedding=query_embedding,
                    limit=3,
                    similarity_threshold=0.5
                )
                
                print(f"\nQuery: '{query}'")
                print(f"Found {len(results)} results:")
                
                for i, doc in enumerate(results, 1):
                    print(f"  {i}. {doc.title} (score: {doc.similarity_score:.3f})")
                    
            except Exception as e:
                print(f"✗ Search test failed for '{query}': {e}")


async def main():
    """Main function to run the ingestion process."""
    # Get the articles directory
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent.parent.parent
    articles_dir = repo_root / 'kb_vacuum_articles'
    
    if not articles_dir.exists():
        print(f"Error: Articles directory not found at {articles_dir}")
        print("Please ensure the kb_vacuum_articles directory exists in the repository root.")
        sys.exit(1)
    
    print(f"Using articles directory: {articles_dir}")
    
    # Create ingester and run
    ingester = VacuumArticleIngester(str(articles_dir))
    
    try:
        # Ingest all articles
        results = await ingester.ingest_all_articles()
        
        # Verify ingestion
        await ingester.verify_ingestion(results)
        
        # Test search
        await ingester.test_search()
        
        # Summary
        successful = sum(1 for doc_id in results.values() if doc_id is not None)
        total = len(results)
        
        print(f"\n=== Ingestion Summary ===")
        print(f"Total files processed: {total}")
        print(f"Successfully ingested: {successful}")
        print(f"Failed: {total - successful}")
        
        if successful > 0:
            print("\n✓ Knowledge base is ready for use!")
        else:
            print("\n✗ No documents were successfully ingested.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Fatal error during ingestion: {e}")
        sys.exit(1)
    
    finally:
        # Clean up
        await db_connection.close()


if __name__ == '__main__':
    asyncio.run(main())