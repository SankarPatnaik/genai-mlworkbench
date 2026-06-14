import os
import math
import re
import uuid
from typing import List, Dict, Any, Union
import numpy as np

# Clients
try:
    import chromadb
except Exception:
    chromadb = None

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except Exception:
    QdrantClient = None
    qmodels = None

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import execute_values
except Exception:
    psycopg2 = None
    sql = None
    execute_values = None

from app.config import settings

INDEX_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,62}$")

def validate_index_name(index_name: str) -> str:
    if not INDEX_NAME_RE.match(index_name or ""):
        raise ValueError("Index names must start with a letter and contain only letters, numbers, hyphens, or underscores, length 3-63.")
    return index_name

def postgres_table_name(index_name: str) -> str:
    return validate_index_name(index_name).replace("-", "_").lower()

# Fallback basic embedding generator using sentence-transformers (local) or mock cosine space
class EmbeddingGenerator:
    @staticmethod
    def get_embeddings(texts: List[str], model_name: str = "default") -> List[List[float]]:
        if model_name not in {"default", "local"}:
            raise ValueError(f"Embedding provider '{model_name}' is configured in the UI but not enabled in this backend build. Use 'default' until provider adapters are wired.")
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

    def add_chunks(self, index_name: str, document_id: str, chunks: List[Dict[str, Any]], embedding_model: str) -> bool:
        raise NotImplementedError

    def search(self, index_name: str, document_id: str, query: str, limit: int, embedding_model: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def health_check(self) -> bool:
        raise NotImplementedError

# ChromaDB adapter
class ChromaService(BaseVectorService):
    def __init__(self):
        if not chromadb:
            raise RuntimeError("chromadb package is not installed")
        # Local Persistent / Ephemeral Chroma client
        self.client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)

    def create_index(self, index_name: str, dimension: int = 384):
        validate_index_name(index_name)
        self.client.get_or_create_collection(name=index_name)

    def add_chunks(self, index_name: str, document_id: str, chunks: List[Dict[str, Any]], embedding_model: str) -> bool:
        validate_index_name(index_name)
        collection = self.client.get_collection(name=index_name)
        texts = [c["text"] for c in chunks]
        embeddings = EmbeddingGenerator.get_embeddings(texts, embedding_model)
        
        ids = [f"{document_id}_chunk_{c['index']}" for c in chunks]
        metadatas = [{"document_id": document_id, "index": c["index"]} for c in chunks]
        
        collection.upsert(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        return True

    def search(self, index_name: str, document_id: str, query: str, limit: int, embedding_model: str) -> List[Dict[str, Any]]:
        validate_index_name(index_name)
        collection = self.client.get_collection(name=index_name)
        query_embeddings = EmbeddingGenerator.get_embeddings([query], embedding_model)
        
        results = collection.query(
            query_embeddings=query_embeddings,
            n_results=limit,
            where={"document_id": document_id}
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
                    "document_id": meta.get("document_id"),
                    "index": meta.get("index"),
                    "similarity": round(similarity, 3)
                })
        return output

    def health_check(self) -> bool:
        self.client.heartbeat()
        return True

# Qdrant adapter
class QdrantService(BaseVectorService):
    def __init__(self):
        if not QdrantClient:
            raise RuntimeError("qdrant-client package is not installed")
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    def create_index(self, index_name: str, dimension: int = 384):
        validate_index_name(index_name)
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

    def add_chunks(self, index_name: str, document_id: str, chunks: List[Dict[str, Any]], embedding_model: str) -> bool:
        validate_index_name(index_name)
        texts = [c["text"] for c in chunks]
        embeddings = EmbeddingGenerator.get_embeddings(texts, embedding_model)
        
        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            points.append(qmodels.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{chunk['index']}")),
                vector=vector,
                payload={"document_id": document_id, "text": chunk["text"], "index": chunk["index"]}
            ))
            
        self.client.upsert(
            collection_name=index_name,
            points=points
        )
        return True

    def search(self, index_name: str, document_id: str, query: str, limit: int, embedding_model: str) -> List[Dict[str, Any]]:
        validate_index_name(index_name)
        query_vector = EmbeddingGenerator.get_embeddings([query], embedding_model)[0]
        
        results = self.client.search(
            collection_name=index_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=document_id)
                    )
                ]
            )
        )
        
        return [
            {
                "text": hit.payload["text"],
                "document_id": hit.payload.get("document_id"),
                "index": hit.payload["index"],
                "similarity": round(hit.score, 3)
            }
            for hit in results
        ]

    def health_check(self) -> bool:
        self.client.get_collections()
        return True

# PostgreSQL / pgvector adapter
class PostgresVectorService(BaseVectorService):
    def __init__(self):
        if not psycopg2:
            raise RuntimeError("psycopg2 package is not installed")
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
        table_name = postgres_table_name(index_name)
        if not isinstance(dimension, int) or dimension <= 0 or dimension > 4096:
            raise ValueError("Vector dimension must be a positive integer up to 4096")
        conn = psycopg2.connect(self.conn_str)
        with conn.cursor() as cur:
            # Create clean tables for collection
            cur.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {} (
                    id SERIAL PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER,
                    content TEXT,
                    embedding vector({})
                );
            """).format(sql.Identifier(table_name), sql.SQL(str(dimension))))
            cur.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (document_id);").format(
                sql.Identifier(f"{table_name}_document_id_idx"),
                sql.Identifier(table_name)
            ))
        conn.commit()
        conn.close()

    def add_chunks(self, index_name: str, document_id: str, chunks: List[Dict[str, Any]], embedding_model: str) -> bool:
        table_name = postgres_table_name(index_name)
        texts = [c["text"] for c in chunks]
        embeddings = EmbeddingGenerator.get_embeddings(texts, embedding_model)
        
        conn = psycopg2.connect(self.conn_str)
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("DELETE FROM {} WHERE document_id = %s;").format(sql.Identifier(table_name)),
                (document_id,)
            )
            
            data = [
                (document_id, chunk["index"], chunk["text"], str(vector))
                for chunk, vector in zip(chunks, embeddings)
            ]
            execute_values(
                cur,
                sql.SQL("INSERT INTO {} (document_id, chunk_index, content, embedding) VALUES %s").format(
                    sql.Identifier(table_name)
                ).as_string(conn),
                data
            )
        conn.commit()
        conn.close()
        return True

    def search(self, index_name: str, document_id: str, query: str, limit: int, embedding_model: str) -> List[Dict[str, Any]]:
        table_name = postgres_table_name(index_name)
        query_vector = EmbeddingGenerator.get_embeddings([query], embedding_model)[0]
        
        conn = psycopg2.connect(self.conn_str)
        with conn.cursor() as cur:
            # Perform Cosine distance query: <=> operator is Cosine Distance in pgvector
            cur.execute(sql.SQL("""
                SELECT content, document_id, chunk_index, 1 - (embedding <=> %s) AS similarity
                FROM {}
                WHERE document_id = %s
                ORDER BY similarity DESC
                LIMIT %s;
            """).format(sql.Identifier(table_name)), (str(query_vector), document_id, limit))
            results = cur.fetchall()
            
        conn.close()
        return [
            {
                "text": r[0],
                "document_id": r[1],
                "index": r[2],
                "similarity": round(float(r[3]), 3) if r[3] is not None else 0.0
            }
            for r in results
        ]

    def health_check(self) -> bool:
        conn = psycopg2.connect(self.conn_str)
        conn.close()
        return True

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
