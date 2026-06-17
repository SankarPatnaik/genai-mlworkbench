# GenAI Workbench Boilerplate Codebase

A low-code/no-code commercialized blueprint for deploying custom Agentic AI workflows and cost-effective Retrieval-Augmented Generation (RAG).

## Tech Stack
- **Frontend:** React + Vite (Vanilla CSS dark theme with glassmorphic cards)
- **Backend:** FastAPI (Python REST API service)
- **Document Store:** AWS S3 / MinIO (S3-compatible API)
- **Vector Databases:** PostgreSQL (`pgvector` extension), ChromaDB, Qdrant
- **Knowledge Graph:** Neo4j with in-memory fallback for local preview
- **PDF/OCR Extraction:** LiteParse, pdfplumber, PyMuPDF rendering, PaddleOCR
- **Agent Orchestration:** LangGraph, Google Antigravity SDK, CrewAI
- **Experiment Tracking:** MLflow Tracking Server

---

## Project Structure
```
genai-workbench/
├── docker-compose.yml       # PostgreSQL + pgvector, Qdrant, Chroma, MinIO, MLflow
├── README.md                # This instructions file
├── backend/
│   ├── requirements.txt     # Python packages dependencies
│   └── app/
│       ├── main.py          # FastAPI server entry point
│       ├── config.py        # Pydantic configuration loader
│       └── services/
│           ├── s3_service.py       # S3 bucket uploads and text extraction
│           ├── chunking_service.py # Text partitioning strategies (Recursive, Semantic, Fixed)
│           ├── vector_service.py   # DB adapters (PostgreSQL, Chroma, Qdrant)
│           ├── agent_service.py    # Framework execution (LangGraph, CrewAI, Google SDK)
│           └── mlflow_service.py   # Flow run logging client
└── frontend/
    ├── index.html           # Single Page App shell
    ├── package.json         # React NPM dependencies
    ├── vite.config.js       # Vite configuration
    └── src/
        ├── main.jsx         # App bootstrapper
        ├── index.css        # CSS variable dark-theme style declarations
        ├── App.jsx          # Stepper coordinator state machine
        └── components/
            ├── Stepper.jsx        # Top progress wizard tracker
            ├── UploadStep.jsx     # Document upload file selector
            ├── ChunkingStep.jsx   # Chunks sliders parameters and highlights
            ├── VectorStep.jsx     # Vector DB settings and index submitter
            ├── AgentStep.jsx      # Prompt editor and LLM parameters
            ├── PlaygroundStep.jsx # Live chat sandbox and metrics tracker
            └── DeployStep.jsx     # Low-code endpoints and Web Widget code
```

---

## Prerequisites
Ensure you have the following installed on your system:
- **Docker & Docker Compose**
- **Python 3.10+**
- **Node.js 18+ & npm**

---

## Getting Started

### 1. Launch Services (Docker)
In the root directory, start the environment dependencies:
```bash
docker compose up -d
```
This launches:
- **MinIO (S3 mockup)** at `http://localhost:9000` (Console at `http://localhost:9001`)
- **Qdrant Vector DB** at `http://localhost:6333`
- **ChromaDB** at `http://localhost:8002`
- **PostgreSQL (pgvector)** at `http://localhost:5432`
- **Neo4j Knowledge Graph** at `http://localhost:7474` (Bolt at `bolt://localhost:7687`)
- **MLflow Tracking Server** at `http://localhost:5001`

### 2. Configure Backend Environment
Create a `.env` file inside the `backend` directory:
```env
# LLM Providers (Required for real API calls, otherwise mock mode executes)
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key

# Storage Credentials (MinIO Defaults)
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadminpassword
AWS_REGION=us-east-1
S3_ENDPOINT_URL=http://localhost:9000
S3_BUCKET_NAME=genai-workbench-docs

# Commercial rollout controls
API_KEY=change-me-before-deploy
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
MAX_UPLOAD_MB=50
ENVIRONMENT=development

# Layout-preserving PDF extraction
PDF_EXTRACTION_STRATEGY=auto
PDF_RENDER_DPI=220
PDF_MAX_PAGES=1000
PDF_MIN_TEXT_CHARS_PER_PAGE=24
PDF_LAYOUT_COLUMNS=120
PDF_MAX_LEADING_SPACES=16
PDF_OCR_LANG=en
PDF_OCR_DEVICE=cpu
PDF_OCR_ENGINE=
PDF_OCR_MIN_CONFIDENCE=0.60
PDF_USE_PADDLE_STRUCTURE=false

# MLflow Configurations
MLFLOW_TRACKING_URI=http://localhost:5001

# Knowledge Graph
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=workbenchpassword
```

### 3. Start the FastAPI Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The FastAPI swagger docs are available at `http://localhost:8000/docs`.

### 4. Start the React Frontend
```bash
cd frontend
npm install
npm run dev
```
Open your browser to `http://localhost:3000` to interact with the dashboard.

For non-local environments, create `frontend/.env`:
```env
VITE_API_BASE_URL=https://your-api-domain.example
VITE_WORKBENCH_API_KEY=change-me-before-deploy
```

---

## Rollout Notes

- API-key protection is enabled when `API_KEY` is set on the backend. Replace this with user authentication and tenant-scoped authorization before public SaaS launch.
- Uploaded documents now receive generated document IDs and namespaced object keys to avoid filename collisions.
- PDF uploads run through a layout-first extraction framework:
  - LiteParse reads native PDF text items and coordinates.
  - pdfplumber enriches fallback text and table detection.
  - PyMuPDF renders pages that need OCR.
  - PaddleOCR extracts scanned or low-text pages and merges OCR boxes back into page coordinates.
  - `/api/v1/documents/{document_id}/layout` returns the retained page, element, bbox, confidence, Markdown, and parser-chain artifact.
- `PDF_EXTRACTION_STRATEGY` supports `auto`, `digital`, `ocr`, and `hybrid`. Use `auto` for normal ingestion, `hybrid` for high-stakes audits where every page should be OCR-checked, and `digital` when PaddleOCR/model startup cost is not acceptable.
- `PDF_USE_PADDLE_STRUCTURE=true` enables PP-StructureV3 document Markdown extraction for richer scanned table/layout parsing. It can download additional PaddleOCR models on first use.
- Vector indexes validate collection names and filter retrieval by `document_id` to avoid cross-document leakage.
- Knowledge graph context builds entity and relationship maps from chunks, using Neo4j when available and memory fallback otherwise. This helps reduce context cost by sending structured graph summaries before larger text chunks.
- The current runtime ships local preview embeddings and mock LLM responses. Hosted model adapters should be added with key vaulting, usage limits, audit logs, and billing controls.
- DOCX/PPTX, Slack, Discord, and web widget delivery are treated as planned connectors until their backend endpoints are implemented.
