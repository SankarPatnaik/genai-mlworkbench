import React from 'react';
import { Terminal, Code, MessageSquare, ShieldAlert } from 'lucide-react';
import { API_BASE_URL } from '../api';

export default function DeployStep({ data }) {
  const curlCode = `curl -X POST "${API_BASE_URL}/api/v1/query" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: <your-workbench-api-key>" \\
  -d '{
    "document_id": "${data.documentId || 'document_name'}",
    "index_name": "${data.indexName || 'workbench-index'}",
    "vector_db": "${data.vectorDb || 'chroma'}",
    "query": "What is the policy limit?",
    "framework": "${data.framework || 'google_sdk'}",
    "system_instruction": "Answer using the context provided...",
    "llm_model": "${data.llmModel || 'local-preview'}"
  }'`;

  const widgetCode = `<script 
  src="${API_BASE_URL}/static/widget.js"
  data-agent-id="${data.documentId || 'agent-id'}"
  data-theme-color="#6366f1"
  async>
</script>`;

  return (
    <div className="step-layout-grid">
      <div className="glass-panel">
        <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
          <Terminal size={20} />
          Low-Code REST API Endpoints
        </h2>
        <p style={{ color: 'var(--secondary-foreground)', fontSize: '0.9rem', marginBottom: '1rem' }}>
          Execute this REST call directly from your server application to invoke the configured Agentic workflow.
        </p>
        <pre style={{ 
          background: 'rgba(0, 0, 0, 0.3)', 
          border: '1px solid var(--border)', 
          borderRadius: 'var(--radius-sm)', 
          padding: '1rem', 
          fontFamily: 'monospace', 
          fontSize: '0.8rem',
          overflowX: 'auto',
          color: '#e4e4e7',
          whiteSpace: 'pre'
        }}>
          {curlCode}
        </pre>

        <h2 style={{ marginTop: '2rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
          <Code size={20} />
          No-Code Web Widget Embed
        </h2>
        <p style={{ color: 'var(--secondary-foreground)', fontSize: '0.9rem', marginBottom: '1rem' }}>
          Widget delivery is a rollout milestone. Add this script after the backend exposes /static/widget.js and token-scoped agent IDs.
        </p>
        <pre style={{ 
          background: 'rgba(0, 0, 0, 0.3)', 
          border: '1px solid var(--border)', 
          borderRadius: 'var(--radius-sm)', 
          padding: '1rem', 
          fontFamily: 'monospace', 
          fontSize: '0.8rem',
          overflowX: 'auto',
          color: '#e4e4e7',
          whiteSpace: 'pre'
        }}>
          {widgetCode}
        </pre>
      </div>

      <div className="glass-panel">
        <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
          <MessageSquare size={20} />
          Third-Party Connectors
        </h2>
        <p style={{ color: 'var(--secondary-foreground)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
          Connect the agentic assistant to corporate platforms:
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ padding: '1rem', background: 'var(--secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.25rem' }}>Slack App Connection</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--secondary-foreground)' }}>
              Planned connector: route Slack events through a signed <code>/api/v1/integrations/slack</code> endpoint.
            </div>
          </div>

          <div style={{ padding: '1rem', background: 'var(--secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.25rem' }}>Discord Bot Token</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--secondary-foreground)' }}>
              Planned connector: store bot tokens in a server-side secret vault before enabling workspace installs.
            </div>
          </div>
        </div>

        <div style={{ 
          marginTop: '2rem', 
          padding: '1rem', 
          background: 'rgba(168, 85, 247, 0.1)', 
          border: '1px solid var(--accent)', 
          borderRadius: 'var(--radius-md)', 
          display: 'flex', 
          gap: '0.75rem',
          alignItems: 'flex-start'
        }}>
          <ShieldAlert size={20} style={{ color: 'var(--accent)', flexShrink: 0 }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--foreground)' }}>Developer Code Export</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--secondary-foreground)', marginTop: '0.25rem' }}>
              Export should generate tenant-scoped code after auth, provider keys, and deployment targets are configured.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
