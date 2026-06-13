# GenAI Workbench Boilerplate Codebase

A low-code/no-code commercialized blueprint for deploying custom Agentic AI workflows and cost-effective Retrieval-Augmented Generation (RAG).

## Tech Stack
- **Frontend:** React + Vite (Vanilla CSS dark theme with glassmorphic cards)
- **Backend:** FastAPI (Python REST API service)
- **Document Store:** AWS S3 / MinIO (S3-compatible API)
- **Vector Databases:** PostgreSQL (`pgvector` extension), ChromaDB, Qdrant
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
- **ChromaDB** at `http://localhost:8000`
- **PostgreSQL (pgvector)** at `http://localhost:5432`
- **MLflow Tracking Server** at `http://localhost:5000`

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

# MLflow Configurations
MLFLOW_TRACKING_URI=http://localhost:5000
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
