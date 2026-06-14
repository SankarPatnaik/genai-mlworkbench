import React from 'react';
import {
  BookOpen,
  CheckCircle2,
  Cloud,
  Database,
  Download,
  ExternalLink,
  GitBranch,
  KeyRound,
  Network,
  PlayCircle,
  Rocket,
  Server,
  ShieldCheck,
  Terminal,
} from 'lucide-react';

const localCommands = [
  {
    title: 'Clone and enter the project',
    command: 'git clone <your-repository-url>\ncd genai-mlworkbench',
  },
  {
    title: 'Start the platform services',
    command: 'docker compose up -d',
  },
  {
    title: 'Start the backend API',
    command: 'cd backend\npython -m venv .venv\nsource .venv/bin/activate\npip install -r requirements.txt\nuvicorn app.main:app --host 127.0.0.1 --port 8000',
  },
  {
    title: 'Start the frontend console',
    command: 'cd frontend\nnpm install\nnpm run dev -- --host 127.0.0.1 --port 3000',
  },
];

const workflowSteps = [
  ['Upload', 'Add PDF, text, markdown, CSV, or supported document files. Workbench extracts text and stores the source document.'],
  ['Chunk', 'Choose chunk size and overlap. Smaller chunks reduce prompt waste; overlap protects answer continuity.'],
  ['Index', 'Select Chroma, Qdrant, or PGVector. The vector index is used for semantic retrieval.'],
  ['Graph', 'Build the context graph. Neo4j links documents, chunks, and entities so queries can use targeted context.'],
  ['Prompt', 'Configure model behavior, temperature, and system instructions for the assistant.'],
  ['Test', 'Ask sample questions, inspect retrieved context, and compare estimated cost before rollout.'],
  ['Deploy', 'Use the REST API, planned widget embed, or connector path for application integration.'],
];

const productionChecklist = [
  ['Set an API key', 'Configure API_KEY so every client request must send X-API-Key.'],
  ['Use managed secrets', 'Keep LLM provider keys, database passwords, and object storage credentials outside the frontend.'],
  ['Enable backups', 'Back up object storage, vector indexes, Postgres, and Neo4j before onboarding customers.'],
  ['Separate tenants', 'Use tenant-scoped indexes, graph labels, storage prefixes, and API credentials.'],
  ['Monitor cost', 'Review token usage, retrieval size, graph context size, and failed requests in MLflow or your observability stack.'],
  ['Harden networking', 'Run behind HTTPS, restrict database ports, and expose only frontend and API ingress.'],
];

function CommandBlock({ item }) {
  return (
    <div className="help-command">
      <div className="help-command-title">{item.title}</div>
      <pre>{item.command}</pre>
    </div>
  );
}

function HelpStat({ icon: Icon, label, value }) {
  return (
    <div className="help-stat">
      <Icon size={18} />
      <div>
        <div className="help-stat-value">{value}</div>
        <div className="help-stat-label">{label}</div>
      </div>
    </div>
  );
}

export default function HelpGuide() {
  return (
    <main className="help-page">
      <section className="help-hero">
        <div className="help-hero-copy">
          <div className="help-eyebrow">
            <BookOpen size={18} />
            Workbench Help Center
          </div>
          <h2>Install, configure, test, and deploy your GenAI Workbench product.</h2>
          <p>
            Follow this guide to move from local installation to a production-ready rollout with vector search,
            Neo4j-powered context graph, cost-aware retrieval, and secure API deployment.
          </p>
          <div className="help-actions">
            <a className="btn btn-primary" href="#installation">
              <PlayCircle size={18} />
              Start setup
            </a>
            <a className="btn btn-secondary" href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
              <ExternalLink size={18} />
              API docs
            </a>
          </div>
        </div>
        <div className="help-hero-panel" aria-label="Workbench platform summary">
          <HelpStat icon={Server} label="Backend API" value="FastAPI" />
          <HelpStat icon={Database} label="Vector stores" value="Chroma, Qdrant, PGVector" />
          <HelpStat icon={Network} label="Context graph" value="Neo4j with fallback" />
          <HelpStat icon={Cloud} label="Object storage" value="S3 / MinIO" />
        </div>
      </section>

      <section id="installation" className="help-section">
        <div className="help-section-header">
          <Terminal size={22} />
          <div>
            <h3>1. Local Installation</h3>
            <p>Use these commands when setting up Workbench on a developer machine or review environment.</p>
          </div>
        </div>
        <img className="help-image" src="/help/install-flow.svg" alt="Workbench installation flow from Docker to backend to frontend" />
        <div className="help-command-grid">
          {localCommands.map((item) => (
            <CommandBlock key={item.title} item={item} />
          ))}
        </div>
      </section>

      <section className="help-section">
        <div className="help-section-header">
          <KeyRound size={22} />
          <div>
            <h3>2. Environment Configuration</h3>
            <p>Configure these settings before real users or customer data are onboarded.</p>
          </div>
        </div>
        <div className="help-table">
          <div><strong>API_BASE_URL</strong><span>Frontend URL for backend API calls. Local default is http://localhost:8000.</span></div>
          <div><strong>API_KEY</strong><span>Server-side key required for secured API traffic. Leave empty only for local demos.</span></div>
          <div><strong>NEO4J_URI</strong><span>Graph database connection used by the Context Graph feature.</span></div>
          <div><strong>S3_ENDPOINT_URL</strong><span>MinIO or S3-compatible storage endpoint for uploaded documents.</span></div>
          <div><strong>MLFLOW_TRACKING_URI</strong><span>Tracking endpoint for experiments, runs, and operational review.</span></div>
        </div>
      </section>

      <section className="help-section">
        <div className="help-section-header">
          <GitBranch size={22} />
          <div>
            <h3>3. Product Workflow</h3>
            <p>The main Workbench wizard is designed around the same sequence customers use to build an assistant.</p>
          </div>
        </div>
        <div className="help-workflow">
          {workflowSteps.map(([title, body], index) => (
            <div className="help-workflow-step" key={title}>
              <div className="help-workflow-number">{index + 1}</div>
              <h4>{title}</h4>
              <p>{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="help-section help-split-section">
        <div>
          <div className="help-section-header">
            <Network size={22} />
            <div>
              <h3>4. Context Graph Setup</h3>
              <p>Build graph context after chunking and indexing to reduce irrelevant LLM context.</p>
            </div>
          </div>
          <div className="help-callout">
            <CheckCircle2 size={20} />
            <p>
              Workbench uses Neo4j when available. If Neo4j is unavailable during a demo, the backend can still use an
              in-memory graph fallback so the flow remains testable.
            </p>
          </div>
          <ol className="help-list">
            <li>Upload a document and generate chunks.</li>
            <li>Index the chunks in your selected vector database.</li>
            <li>Open Context Graph and select Build Graph.</li>
            <li>Ask questions in Playground with graph context enabled.</li>
          </ol>
        </div>
        <img className="help-image compact" src="/help/knowledge-graph.svg" alt="Knowledge graph connecting documents, entities, and targeted context" />
      </section>

      <section className="help-section help-split-section">
        <img className="help-image compact" src="/help/deployment-flow.svg" alt="Production deployment flow for Workbench" />
        <div>
          <div className="help-section-header">
            <Rocket size={22} />
            <div>
              <h3>5. Deployment Readiness</h3>
              <p>Use this checklist before moving a tenant from demo to production.</p>
            </div>
          </div>
          <div className="help-checklist">
            {productionChecklist.map(([title, body]) => (
              <div className="help-check" key={title}>
                <ShieldCheck size={18} />
                <div>
                  <strong>{title}</strong>
                  <span>{body}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="help-section">
        <div className="help-section-header">
          <Download size={22} />
          <div>
            <h3>6. Customer Handover</h3>
            <p>Share these URLs after deployment so reviewers know where to go.</p>
          </div>
        </div>
        <div className="help-link-grid">
          <a href="http://localhost:3000/" target="_blank" rel="noreferrer">Workbench console<span>http://localhost:3000</span></a>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API documentation<span>http://localhost:8000/docs</span></a>
          <a href="http://localhost:7474" target="_blank" rel="noreferrer">Neo4j browser<span>http://localhost:7474</span></a>
          <a href="http://localhost:5001" target="_blank" rel="noreferrer">MLflow tracking<span>http://localhost:5001</span></a>
        </div>
      </section>
    </main>
  );
}
