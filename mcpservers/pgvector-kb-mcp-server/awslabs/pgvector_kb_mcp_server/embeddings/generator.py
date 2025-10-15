# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Text embedding generation for pgvector knowledge base."""

import os
from typing import List, Optional
import numpy as np
import boto3
from sentence_transformers import SentenceTransformer
from loguru import logger


class EmbeddingGenerator:
    """Generates text embeddings using various models."""
    
    def __init__(self):
        self._model: Optional[SentenceTransformer] = None
        self._bedrock_client = None
        self._embedding_model = os.getenv('EMBEDDING_MODEL', 'sentence-transformers')
        
    async def initialize(self) -> None:
        """Initialize the embedding model."""
        if self._embedding_model == 'sentence-transformers':
            await self._initialize_sentence_transformer()
        elif self._embedding_model.startswith('amazon.titan'):
            await self._initialize_bedrock()
        else:
            raise ValueError(f'Unsupported embedding model: {self._embedding_model}')
    
    async def _initialize_sentence_transformer(self) -> None:
        """Initialize sentence transformer model."""
        if self._model is not None:
            return
            
        model_name = os.getenv('SENTENCE_TRANSFORMER_MODEL', 'all-MiniLM-L6-v2')
        self._model = SentenceTransformer(model_name)
        logger.info(f'Sentence transformer model {model_name} initialized')
    
    async def _initialize_bedrock(self) -> None:
        """Initialize Bedrock client for embeddings."""
        if self._bedrock_client is not None:
            return
            
        region = os.getenv('AWS_REGION', 'us-west-2')
        self._bedrock_client = boto3.client('bedrock-runtime', region_name=region)
        logger.info(f'Bedrock client initialized for region {region}')
    
    async def generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        if not text.strip():
            raise ValueError('Text cannot be empty')
            
        if self._embedding_model == 'sentence-transformers':
            return await self._generate_sentence_transformer_embedding(text)
        elif self._embedding_model.startswith('amazon.titan'):
            return await self._generate_bedrock_embedding(text)
        else:
            raise ValueError(f'Unsupported embedding model: {self._embedding_model}')
    
    async def generate_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts."""
        if self._embedding_model == 'sentence-transformers':
            return await self._generate_sentence_transformer_embeddings(texts)
        else:
            # For other models, generate one by one
            embeddings = []
            for text in texts:
                embedding = await self.generate_embedding(text)
                embeddings.append(embedding)
            return embeddings
    
    async def _generate_sentence_transformer_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using sentence transformer."""
        if not self._model:
            await self._initialize_sentence_transformer()
            
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding
    
    async def _generate_sentence_transformer_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts using sentence transformer."""
        if not self._model:
            await self._initialize_sentence_transformer()
            
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [embedding for embedding in embeddings]
    
    async def _generate_bedrock_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using Amazon Bedrock."""
        if not self._bedrock_client:
            await self._initialize_bedrock()
            
        try:
            import json
            
            body = json.dumps({
                'inputText': text
            })
            
            response = self._bedrock_client.invoke_model(
                modelId=self._embedding_model,
                body=body,
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            embedding = np.array(response_body['embedding'], dtype=np.float32)
            
            return embedding
            
        except Exception as e:
            logger.error(f'Failed to generate Bedrock embedding: {e}')
            raise
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by the current model."""
        if self._embedding_model == 'sentence-transformers':
            model_name = os.getenv('SENTENCE_TRANSFORMER_MODEL', 'all-MiniLM-L6-v2')
            # Common dimensions for sentence transformer models
            dimensions = {
                'all-MiniLM-L6-v2': 384,
                'all-MiniLM-L12-v2': 384,
                'all-mpnet-base-v2': 768,
                'multi-qa-MiniLM-L6-cos-v1': 384,
            }
            return dimensions.get(model_name, 384)  # Default to 384
        elif self._embedding_model == 'amazon.titan-embed-text-v1':
            return 1536
        else:
            return 384  # Default dimension


# Global embedding generator instance
embedding_generator = EmbeddingGenerator()