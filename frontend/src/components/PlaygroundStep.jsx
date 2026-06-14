import React, { useState } from 'react';
import { Send, BarChart2, FileSymlink, ExternalLink } from 'lucide-react';
import { apiHeaders, apiUrl, parseApiError } from '../api';

export default function PlaygroundStep({ data }) {
  const [messages, setMessages] = useState([
    { sender: 'assistant', text: "Hello! Test the document retrieval capabilities by asking me questions about your uploaded documents." }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [retrievedChunks, setRetrievedChunks] = useState([]);
  const [steps, setSteps] = useState([]);
  const [metrics, setMetrics] = useState(null);

  const sendMessage = async () => {
    if (!input.trim()) return;
    
    const userMessage = { sender: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(apiUrl("/api/v1/query"), {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          document_id: data.documentId || "",
          index_name: data.indexName || "workbench-index",
          vector_db: data.vectorDb || "chroma",
          query: input,
          framework: data.framework || "google_sdk",
          system_instruction: data.systemInstruction || "",
          llm_model: data.llmModel || "local-preview",
          top_k: data.topK || 3,
          embedding_model: data.embeddingModel || "default",
          temperature: data.temperature || 0.7
        }),
      });

      if (!response.ok) {
        throw new Error(await parseApiError(response, "Failed to process query response"));
      }

      const result = await response.json();
      setMessages(prev => [...prev, { sender: 'assistant', text: result.response }]);
      setRetrievedChunks(result.retrieved_chunks || []);
      setSteps(result.steps || []);
      setMetrics(result.metrics || null);
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'assistant', text: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="playground-grid">
      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', padding: '1.5rem' }}>
        <h2 style={{ marginBottom: '1rem', fontSize: '1.2rem' }}>Agent Playground</h2>
        
        <div className="chat-window">
          <div className="chat-messages">
            {messages.map((m, idx) => (
              <div 
                key={idx} 
                className={`message-bubble ${m.sender === 'user' ? 'message-user' : 'message-assistant'}`}
              >
                {m.text}
              </div>
            ))}
            {loading && (
              <div className="message-bubble message-assistant" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <div className="spinner"></div>
                Thinking...
              </div>
            )}
          </div>
          <div className="chat-input-area">
            <input 
              type="text" 
              placeholder="Ask a question about your indexed files..." 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
              disabled={loading}
            />
            <button className="btn btn-primary" onClick={sendMessage} disabled={loading}>
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>

      <div className="metrics-panel">
        {/* MLflow & Run Metrics */}
        <div className="glass-panel">
          <h2 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
            <BarChart2 size={18} style={{ color: 'var(--primary)' }} />
            Run Execution Metrics
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginHeight: '10px' }}>
            <div className="metric-card">
              <div style={{ fontSize: '0.75rem', color: 'var(--secondary-foreground)' }}>LATENCY</div>
              <div className="metric-value">{metrics ? `${metrics.latency_ms}ms` : '0ms'}</div>
            </div>
            <div className="metric-card">
              <div style={{ fontSize: '0.75rem', color: 'var(--secondary-foreground)' }}>COST</div>
              <div className="metric-value">{metrics ? `$${(metrics.prompt_cost + metrics.completion_cost).toFixed(6)}` : '$0.00'}</div>
            </div>
          </div>

          {metrics && metrics.mlflow_url && (
            <a 
              href={metrics.mlflow_url} 
              target="_blank" 
              rel="noreferrer"
              className="btn btn-secondary"
              style={{ width: '100%', marginTop: '1.5rem', display: 'inline-flex', gap: '0.5rem', fontSize: '0.85rem' }}
            >
              View Flow Run in MLflow
              <ExternalLink size={14} />
            </a>
          )}
        </div>

        {/* Retrieved Context Blocks */}
        <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <h2 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
            <FileSymlink size={18} style={{ color: 'var(--accent)' }} />
            Retrieved Context Chunks
          </h2>

          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '230px' }}>
            {retrievedChunks.length > 0 ? (
              retrievedChunks.map((chunk, idx) => (
                <div key={idx} style={{ 
                  background: 'var(--secondary)', 
                  border: '1px solid var(--border)', 
                  borderRadius: 'var(--radius-sm)', 
                  padding: '0.75rem' 
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--secondary-foreground)', marginBottom: '0.25rem' }}>
                    <span>CHUNK #{chunk.index}</span>
                    <span style={{ color: 'var(--success)' }}>Similarity: {chunk.similarity}</span>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#e4e4e7', display: '-webkit-box', WebkitLineClamp: '3', WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {chunk.text}
                  </div>
                </div>
              ))
            ) : (
              <div style={{ color: 'var(--muted-foreground)', textAlign: 'center', fontSize: '0.85rem', padding: '1rem' }}>
                No chunks retrieved yet. Submit a query to test retrieval logic.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
