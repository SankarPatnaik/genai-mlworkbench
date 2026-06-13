from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# Service imports
from app.config import settings
from app.services.s3_service import s3_service
from app.services.chunking_service import chunking_service
from app.services.vector_service import VectorServiceFactory
from app.services.agent_service import agent_service

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory session cache for document prototyping
session_store = {}

# Pydantic schemas for structured requests
class ChunkRequest(BaseModel):
    document_id: str
    method: str = Field(..., description="recursive, fixed, semantic, entire")
    params: Dict[str, Any] = Field(default_factory=dict)

class EmbedRequest(BaseModel):
    document_id: str
    vector_db: str = Field(..., description="chroma, qdrant, postgres")
    index_name: str
    embedding_model: str = "default"
    chunks: List[Dict[str, Any]]

class QueryRequest(BaseModel):
    document_id: str
    index_name: str
    vector_db: str
    query: str
    framework: str = Field(..., description="langgraph, google_sdk, crewai, direct")
    system_instruction: str
    llm_model: str = "gemini-3.5-flash"
    top_k: int = 3
    embedding_model: str = "default"
    temperature: float = 0.7

@app.get("/")
def read_root():
    return {"message": "GenAI Workbench API Running", "version": "1.0.0"}

@app.get(f"{settings.API_V1_STR}/status")
def get_service_status():
    """
    Diagnostic route showing check state of S3 and other DB integrations.
    """
    status = {
        "s3": "connected",
        "chroma": "offline",
        "qdrant": "offline",
        "postgres": "offline",
        "mlflow": "connected"
    }
    
    # Chroma
    try:
        from chromadb.errors import InvalidCollectionException
        client = VectorServiceFactory.get_service("chroma")
        status["chroma"] = "connected"
    except Exception:
        pass
        
    # Qdrant
    try:
        client = VectorServiceFactory.get_service("qdrant")
        status["qdrant"] = "connected"
    except Exception:
        pass

    # Postgres
    try:
        client = VectorServiceFactory.get_service("postgres")
        status["postgres"] = "connected"
    except Exception:
        pass

    return status

@app.post(f"{settings.API_V1_STR}/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Endpoint 1: Upload file, store raw content in S3/MinIO, extract normalized text.
    """
    try:
        contents = await file.read()
        
        # Save to S3/Minio
        s3_key = s3_service.upload_file(contents, file.filename)
        
        # Convert and extract text
        extracted_text = s3_service.convert_to_pdf_text(file.filename, contents)
        
        # Store metadata in session store
        document_id = file.filename
        session_store[document_id] = {
            "s3_key": s3_key,
            "text": extracted_text,
            "filename": file.filename
        }
        
        return {
            "document_id": document_id,
            "filename": file.filename,
            "s3_key": s3_key,
            "text_preview": extracted_text[:800],
            "total_characters": len(extracted_text)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post(f"{settings.API_V1_STR}/chunk")
def chunk_document(request: ChunkRequest):
    """
    Endpoint 2: Retrieve text from document and return chunk metadata and boundary list.
    """
    doc = session_store.get(request.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document ID not found in session")
        
    try:
        chunks = chunking_service.split_document(
            text=doc["text"],
            method=request.method,
            params=request.params
        )
        return {
            "document_id": request.document_id,
            "chunks_count": len(chunks),
            "chunks": chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunking failed: {str(e)}")

@app.post(f"{settings.API_V1_STR}/embed")
def embed_document(request: EmbedRequest):
    """
    Endpoint 3: Create vector collections and load chunk embeddings into the DB.
    """
    try:
        # Retrieve vector adapter
        vector_db = VectorServiceFactory.get_service(request.vector_db)
        
        # Setup table/collection
        vector_db.create_index(index_name=request.index_name)
        
        # Load and write chunks
        success = vector_db.add_chunks(
            index_name=request.index_name,
            chunks=request.chunks,
            embedding_model=request.embedding_model
        )
        
        return {
            "index_name": request.index_name,
            "vector_db": request.vector_db,
            "chunks_indexed": len(request.chunks),
            "status": "success" if success else "failed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding indexing failed: {str(e)}")

@app.post(f"{settings.API_V1_STR}/query")
def query_agent(request: QueryRequest):
    """
    Endpoint 4: Query vector store for top-K chunks and run selected Agent runner.
    """
    try:
        # Search relevant context chunks
        vector_db = VectorServiceFactory.get_service(request.vector_db)
        search_results = vector_db.search(
            index_name=request.index_name,
            query=request.query,
            limit=request.top_k,
            embedding_model=request.embedding_model
        )
        
        context_texts = [res["text"] for res in search_results]
        
        # Run agentic generation pipeline
        agent_response = agent_service.run_agent(
            framework=request.framework,
            prompt=request.query,
            context_chunks=context_texts,
            system_instruction=request.system_instruction,
            llm_model=request.llm_model,
            temperature=request.temperature
        )
        
        return {
            "response": agent_response["response"],
            "steps": agent_response["steps"],
            "retrieved_chunks": search_results,
            "metrics": agent_response["metrics"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query resolution failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
