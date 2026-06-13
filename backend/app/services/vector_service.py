import os
import math
from typing import List, Dict, Any, Union
import numpy as np

# Clients
import chromadb
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
import psycopg2
from psycopg2.extras import execute_values

from app.config import settings

# Fallback basic embedding generator using sentence-transformers (local) or mock cosine space
class EmbeddingGenerator:
    @staticmethod
    def get_embeddings(texts: List[str], model_name: str = "default") -> List[List[float]]:
        # Check for OpenAI or Gemini API usage if configured
        # For simplicity and offline capability in the boilerplate, we check local dependencies
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = model.encode(texts)
            return [e.tolist() for e in embeddings]
        except Exception:
            # Simple mock hashing embedding generator for zero-setup compilation
            # Returns a deterministic pseudo-random unit vector based on characters
            embeddings = []
            dim = 384
            for text in texts:
                np.random.seed(abs(hash(text)) % (2**32))
                vec = np.random.randn(dim)
                vec /= np.linalg.norm(vec)
                embeddings.append(vec.tolist())
            return embeddings

class BaseVectorService:
    def create_index(self, index_name: str, dimension: int = 384):
        raise NotImplementedError

    def add_chunks(self, index_name: str, chunks: List[Dict[str, Any]], embedding_model: str) -> bool:
        raise NotImplementedError

    def search(self, index_name: str, query: str, limit: int, embedding_model: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

# ChromaDB adapter
class ChromaService(BaseVectorService):
    def __init__(self):
        # Local Persistent / Ephemeral Chroma client
        self.client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)

    def create_index(self, index_name: str, dimension: int = 384):
        self.client.get_or_create_collection(name=index_name)

    def add_chunks(self, index_name: str, chunks: List[Dict[str, Any]], embedding_model: str) -> bool:
        collection = self.client.get_collection(name=index_name)
        texts = [c["text"] for c in chunks]
        embeddings = EmbeddingGenerator.get_embeddings(texts, embedding_model)
        
        ids = [f"chunk_{c['index']}" for c in chunks]
        metadatas = [{"index": c["index"]} for c in chunks]
        
        collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        return True

    def search(self, index_name: str, query: str, limit: int, embedding_model: str) -> List[Dict[str, Any]]:
        collection = self.client.get_collection(name=index_name)
        query_embeddings = EmbeddingGenerator.get_embeddings([query], embedding_model)
        
        results = collection.query(
            query_embeddings=query_embeddings,
            n_results=limit
        )
        
        output = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            distances = results["distances"][0] if "distances" in results else [0.0] * len(docs)
            for doc, meta, dist in zip(docs, metas, distances):
                # Convert distance to a similarity score (0 to 1 range)
                similarity = 1.0 - (dist / 2.0) if dist <= 2.0 else 0.0
                output.append({
                    "text": doc,
                    "index": meta.get("index"),
                    "similarity": round(similarity, 3)
                })
        return output

# Qdrant adapter
class QdrantService(BaseVectorService):
    def __init__(self):
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    def create_index(self, index_name: str, dimension: int = 384):
        # Recreate collection if not exists
        try:
            self.client.get_collection(collection_name=index_name)
        except Exception:
            self.client.create_collection(
                collection_name=index_name,
                vectors_config=qmodels.VectorParams(
                    size=dimension,
                    distance=qmodels.Distance.COSINE
                )
            )

    def add_chunks(self, index_name: str, chunks: List[Dict[str, Any]], embedding_model: str) -> bool:
        texts = [c["text"] for c in chunks]
        embeddings = EmbeddingGenerator.get_embeddings(texts, embedding_model)
        
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            points.append(qmodels.PointStruct(
                id=chunk["index"],
                vector=vector,
                payload={"text": chunk["text"], "index": chunk["index"]}
            ))
            
        self.client.upsert(
            collection_name=index_name,
            points=points
        )
        return True

    def search(self, index_name: str, query: str, limit: int, embedding_model: str) -> List[Dict[str, Any]]:
        query_vector = EmbeddingGenerator.get_embeddings([query], embedding_model)[0]
        
        results = self.client.search(
            collection_name=index_name,
            query_vector=query_vector,
            limit=limit
        )
        
        return [
            {
                "text": hit.payload["text"],
                "index": hit.payload["index"],
                "similarity": round(hit.score, 3)
            }
            for hit in results
        ]

# PostgreSQL / pgvector adapter
class PostgresVectorService(BaseVectorService):
    def __init__(self):
        self.conn_str = f"dbname={settings.POSTGRES_DB} user={settings.POSTGRES_USER} password={settings.POSTGRES_PASSWORD} host={settings.POSTGRES_HOST} port={settings.POSTGRES_PORT}"
        self._ensure_extension()

    def _ensure_extension(self):
        try:
            conn = psycopg2.connect(self.conn_str)
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Postgres Connection failed: {e}. Ensure docker services are running.")

    def create_index(self, index_name: str, dimension: int = 384):
        conn = psycopg2.connect(self.conn_str)
        with conn.cursor() as cur:
            # Create clean tables for collection
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {index_name} (
                    id SERIAL PRIMARY KEY,
                    chunk_index INTEGER,
                    content TEXT,
                    embedding vector({dimension})
                );
            """)
        conn.commit()
        conn.close()

    def add_chunks(self, index_name: str, chunks: List[Dict[str, Any]], embedding_model: str) -> bool:
        texts = [c["text"] for c in chunks]
        embeddings = EmbeddingGenerator.get_embeddings(texts, embedding_model)
        
        conn = psycopg2.connect(self.conn_str)
        with conn.cursor() as cur:
            # Truncate to avoid duplicates during prototyping
            cur.execute(f"TRUNCATE TABLE {index_name};")
            
            data = [
                (chunk["index"], chunk["text"], str(vector))
                for chunk, vector in zip(chunks, embeddings)
            ]
            execute_values(
                cur,
                f"INSERT INTO {index_name} (chunk_index, content, embedding) VALUES %s",
                data
            )
        conn.commit()
        conn.close()
        return True

    def search(self, index_name: str, query: str, limit: int, embedding_model: str) -> List[Dict[str, Any]]:
        query_vector = EmbeddingGenerator.get_embeddings([query], embedding_model)[0]
        
        conn = psycopg2.connect(self.conn_str)
        with conn.cursor() as cur:
            # Perform Cosine distance query: <=> operator is Cosine Distance in pgvector
            cur.execute(f"""
                SELECT content, chunk_index, 1 - (embedding <=> %s) AS similarity
                FROM {index_name}
                ORDER BY similarity DESC
                LIMIT %s;
            """, (str(query_vector), limit))
            results = cur.fetchall()
            
        conn.close()
        return [
            {
                "text": r[0],
                "index": r[1],
                "similarity": round(float(r[2]), 3) if r[2] is not None else 0.0
            }
            for r in results
        ]

# Simple Factory Pattern
class VectorServiceFactory:
    @staticmethod
    def get_service(provider: str) -> BaseVectorService:
        prov = provider.lower()
        if prov == "chroma":
            return ChromaService()
        elif prov == "qdrant":
            return QdrantService()
        elif prov == "postgres" or prov == "postgresql":
            return PostgresVectorService()
        else:
            raise ValueError(f"Unsupported Vector Database provider: {provider}")
