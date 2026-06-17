import os
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
load_dotenv()

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "GenAI Workbench Backend"
    PORT: int = 8000
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    API_KEY: str = os.getenv("API_KEY", "")
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", 50))
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")

    # PDF/OCR extraction configuration
    PDF_EXTRACTION_STRATEGY: str = os.getenv("PDF_EXTRACTION_STRATEGY", "auto").lower()
    PDF_RENDER_DPI: int = int(os.getenv("PDF_RENDER_DPI", 220))
    PDF_MAX_PAGES: int = int(os.getenv("PDF_MAX_PAGES", 1000))
    PDF_MIN_TEXT_CHARS_PER_PAGE: int = int(os.getenv("PDF_MIN_TEXT_CHARS_PER_PAGE", 24))
    PDF_LAYOUT_COLUMNS: int = int(os.getenv("PDF_LAYOUT_COLUMNS", 120))
    PDF_MAX_LEADING_SPACES: int = int(os.getenv("PDF_MAX_LEADING_SPACES", 16))
    PDF_OCR_LANG: str = os.getenv("PDF_OCR_LANG", "en")
    PDF_OCR_DEVICE: str = os.getenv("PDF_OCR_DEVICE", "cpu")
    PDF_OCR_ENGINE: str = os.getenv("PDF_OCR_ENGINE", "")
    PDF_OCR_MIN_CONFIDENCE: float = float(os.getenv("PDF_OCR_MIN_CONFIDENCE", 0.60))
    PDF_USE_PADDLE_STRUCTURE: bool = os.getenv("PDF_USE_PADDLE_STRUCTURE", "false").lower() in {"1", "true", "yes"}
    
    # LLM Provider Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")

    # S3 Storage Config (MinIO default for local testing)
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadminpassword")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "genai-workbench-docs")

    # Vector Databases configurations
    # Chroma
    CHROMA_HOST: str = os.getenv("CHROMA_HOST", "localhost")
    CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", 8002))
    
    # Qdrant
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", 6333))
    
    # PostgreSQL / pgvector
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgrespassword")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "genai_workbench")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", 5432))

    # MLflow tracking Config
    MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")

    # Knowledge graph configuration
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "workbenchpassword")

    class Config:
        case_sensitive = True

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

settings = Settings()
