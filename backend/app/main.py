import secrets
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# Service imports
from app.config import settings
from app.services.s3_service import s3_service, safe_filename
from app.services.pdf_extraction_service import pdf_extraction_service
from app.services.chunking_service import chunking_service
from app.services.vector_service import VectorServiceFactory, validate_index_name
from app.services.agent_service import agent_service
from app.services.mlflow_service import mlflow_service
from app.services.knowledge_graph_service import knowledge_graph_service

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Replace this with durable tenant-scoped metadata before horizontal scaling.
session_store = {}

def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if not settings.API_KEY:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# Pydantic schemas for structured requests
class ChunkRequest(BaseModel):
    document_id: str
    method: str = Field(..., description="recursive, fixed, semantic, entire")
    params: Dict[str, Any] = Field(default_factory=dict)

class EmbedRequest(BaseModel):
    document_id: str
    vector_db: str = Field(..., description="chroma, qdrant, postgres")
    index_name: str = Field(..., min_length=3, max_length=63)
    embedding_model: str = "default"
    chunks: List[Dict[str, Any]]

class GraphBuildRequest(BaseModel):
    document_id: str
    chunks: List[Dict[str, Any]]
    max_entities_per_chunk: int = 12

class GraphQueryRequest(BaseModel):
    document_id: str
    query: str
    max_entities: int = 8
    max_chunks: int = 3

class QueryRequest(BaseModel):
    document_id: str
    index_name: str
    vector_db: str
    query: str
    framework: str = Field(..., description="langgraph, google_sdk, crewai, direct")
    system_instruction: str
    llm_model: str = "local-preview"
    top_k: int = 3
    embedding_model: str = "default"
    temperature: float = 0.7
    use_graph_context: bool = True
    graph_max_entities: int = 8

@app.get("/")
def read_root():
    return {"message": "GenAI Workbench API Running", "version": "1.0.0"}

@app.get(f"{settings.API_V1_STR}/status")
def get_service_status():
    """
    Diagnostic route showing check state of S3 and other DB integrations.
    """
    status = {
        "s3": "offline",
        "chroma": "offline",
        "qdrant": "offline",
        "postgres": "offline",
        "knowledge_graph": "memory",
        "mlflow": "offline",
        "auth": "enabled" if settings.API_KEY else "disabled",
        "environment": settings.ENVIRONMENT,
    }

    if s3_service.is_available():
        status["s3"] = "connected"
    
    # Chroma
    try:
        client = VectorServiceFactory.get_service("chroma")
        client.health_check()
        status["chroma"] = "connected"
    except Exception:
        pass
        
    # Qdrant
    try:
        client = VectorServiceFactory.get_service("qdrant")
        client.health_check()
        status["qdrant"] = "connected"
    except Exception:
        pass

    # Postgres
    try:
        client = VectorServiceFactory.get_service("postgres")
        client.health_check()
        status["postgres"] = "connected"
    except Exception:
        pass

    if mlflow_service.is_available():
        status["mlflow"] = "connected"

    status["knowledge_graph"] = "neo4j" if knowledge_graph_service.is_available() else "memory"

    return status

@app.post(f"{settings.API_V1_STR}/upload")
async def upload_document(file: UploadFile = File(...), _: None = Depends(require_api_key)):
    """
    Endpoint 1: Upload file, store raw content in S3/MinIO, extract normalized text.
    """
    try:
        contents = await file.read()
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if len(contents) > max_bytes:
            raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_MB}MB upload limit")

        filename = safe_filename(file.filename or "document")
        document_id = uuid.uuid4().hex
        object_key = f"documents/{document_id}/{filename}"
        
        # Save to S3/Minio
        s3_key = s3_service.upload_file(contents, object_key)
        
        # Extract layout-preserving text and page structure.
        extraction = pdf_extraction_service.extract_document(filename, contents)
        extracted_text = extraction["text"]
        if not extracted_text.strip():
            raise ValueError("No readable text was extracted from this document")
        
        # Store metadata in session store
        session_store[document_id] = {
            "s3_key": s3_key,
            "text": extracted_text,
            "layout_text": extraction["layout_text"],
            "markdown": extraction["markdown"],
            "extraction": extraction,
            "filename": filename,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        extraction_summary = {
            "profile": extraction["metadata"]["profile"],
            "page_count": extraction["metadata"]["page_count"],
            "parser_chain": extraction["metadata"]["parser_chain"],
            "layout_preserved": extraction["metadata"]["layout_preserved"],
            "element_count": extraction["metadata"]["element_count"],
            "low_confidence_ocr_elements": extraction["metadata"]["low_confidence_ocr_elements"],
            "warnings": extraction["warnings"][:5],
        }

        return {
            "document_id": document_id,
            "filename": filename,
            "s3_key": s3_key,
            "text_preview": extracted_text[:800],
            "total_characters": len(extracted_text),
            "extraction_summary": extraction_summary,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get(f"{settings.API_V1_STR}/documents/{{document_id}}/layout")
def get_document_layout(document_id: str, _: None = Depends(require_api_key)):
    """
    Retrieve the full layout-preserving extraction artifact for a document.
    """
    doc = session_store.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document ID not found in session")
    return {
        "document_id": document_id,
        "filename": doc["filename"],
        "extraction": doc["extraction"],
    }

@app.post(f"{settings.API_V1_STR}/chunk")
def chunk_document(request: ChunkRequest, _: None = Depends(require_api_key)):
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
def embed_document(request: EmbedRequest, _: None = Depends(require_api_key)):
    """
    Endpoint 3: Create vector collections and load chunk embeddings into the DB.
    """
    try:
        if request.document_id not in session_store:
            raise HTTPException(status_code=404, detail="Document ID not found in session")
        validate_index_name(request.index_name)

        # Retrieve vector adapter
        vector_db = VectorServiceFactory.get_service(request.vector_db)
        
        # Setup table/collection
        vector_db.create_index(index_name=request.index_name)
        
        # Load and write chunks
        success = vector_db.add_chunks(
            index_name=request.index_name,
            document_id=request.document_id,
            chunks=request.chunks,
            embedding_model=request.embedding_model
        )
        
        return {
            "index_name": request.index_name,
            "document_id": request.document_id,
            "vector_db": request.vector_db,
            "chunks_indexed": len(request.chunks),
            "status": "success" if success else "failed"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding indexing failed: {str(e)}")

@app.post(f"{settings.API_V1_STR}/graph/build")
def build_knowledge_graph(request: GraphBuildRequest, _: None = Depends(require_api_key)):
    """
    Endpoint 4: Build a document-scoped context graph that can reduce retrieval token load.
    """
    try:
        if request.document_id not in session_store:
            raise HTTPException(status_code=404, detail="Document ID not found in session")
        if request.max_entities_per_chunk < 3 or request.max_entities_per_chunk > 30:
            raise HTTPException(status_code=400, detail="max_entities_per_chunk must be between 3 and 30")

        summary = knowledge_graph_service.build_graph(
            document_id=request.document_id,
            chunks=request.chunks,
            max_entities_per_chunk=request.max_entities_per_chunk,
        )
        return {"status": "success", **summary}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Knowledge graph build failed: {str(e)}")

@app.post(f"{settings.API_V1_STR}/graph/query")
def query_knowledge_graph(request: GraphQueryRequest, _: None = Depends(require_api_key)):
    """
    Endpoint 5: Query the context graph for compact entity and relationship context.
    """
    try:
        if request.max_entities < 1 or request.max_entities > 30:
            raise HTTPException(status_code=400, detail="max_entities must be between 1 and 30")
        if request.max_chunks < 0 or request.max_chunks > 10:
            raise HTTPException(status_code=400, detail="max_chunks must be between 0 and 10")
        return knowledge_graph_service.query_context(
            document_id=request.document_id,
            query=request.query,
            max_entities=request.max_entities,
            max_chunks=request.max_chunks,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Knowledge graph query failed: {str(e)}")

@app.post(f"{settings.API_V1_STR}/query")
def query_agent(request: QueryRequest, _: None = Depends(require_api_key)):
    """
    Endpoint 4: Query vector store for top-K chunks and run selected Agent runner.
    """
    try:
        validate_index_name(request.index_name)
        if request.top_k < 1 or request.top_k > 20:
            raise HTTPException(status_code=400, detail="top_k must be between 1 and 20")

        # Search relevant context chunks
        vector_db = VectorServiceFactory.get_service(request.vector_db)
        search_results = vector_db.search(
            index_name=request.index_name,
            document_id=request.document_id,
            query=request.query,
            limit=request.top_k,
            embedding_model=request.embedding_model
        )
        
        graph_context = None
        context_texts = [res["text"] for res in search_results]
        if request.use_graph_context:
            graph_context = knowledge_graph_service.query_context(
                document_id=request.document_id,
                query=request.query,
                max_entities=request.graph_max_entities,
                max_chunks=0,
            )
            if graph_context["context_summary"]:
                context_texts = [f"Knowledge graph context:\n{graph_context['context_summary']}"] + context_texts
        
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
            "graph_context": graph_context,
            "metrics": agent_response["metrics"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query resolution failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
