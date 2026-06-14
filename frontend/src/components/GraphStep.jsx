import React, { useState } from 'react';
import { GitBranch, CheckCircle, RefreshCw, Network } from 'lucide-react';
import { apiHeaders, apiUrl, parseApiError } from '../api';

export default function GraphStep({ data, updateData }) {
  const [maxEntitiesPerChunk, setMaxEntitiesPerChunk] = useState(data.maxEntitiesPerChunk || 12);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(data.graphSummary || null);

  const buildGraph = async () => {
    if (!data.documentId || !data.chunks || data.chunks.length === 0) {
      setError("Upload and chunk a document before building a context graph.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(apiUrl("/api/v1/graph/build"), {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          document_id: data.documentId,
          chunks: data.chunks,
          max_entities_per_chunk: maxEntitiesPerChunk,
        }),
      });

      if (!response.ok) {
        throw new Error(await parseApiError(response, "Failed to build knowledge graph"));
      }

      const result = await response.json();
      setSummary(result);
      updateData({
        graphEnabled: true,
        graphSummary: result,
        maxEntitiesPerChunk,
      });
    } catch (err) {
      setError(err.message || "An error occurred while building the context graph.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="step-layout-grid">
      <div className="glass-panel">
        <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
          <GitBranch size={20} />
          Knowledge Graph Context
        </h2>

        <p style={{ color: 'var(--secondary-foreground)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
          Build a compact entity and relationship map so queries can start with structured context before sending larger chunks to the model.
        </p>

        <div className="form-group">
          <label>Entity Budget per Chunk: {maxEntitiesPerChunk}</label>
          <input
            type="range"
            min={3}
            max={30}
            step={1}
            value={maxEntitiesPerChunk}
            onChange={(e) => setMaxEntitiesPerChunk(parseInt(e.target.value))}
          />
        </div>

        <button
          className="btn btn-primary"
          style={{ width: '100%', marginTop: '1.5rem' }}
          onClick={buildGraph}
          disabled={loading || !data.chunks || data.chunks.length === 0}
        >
          {loading ? (
            <>
              <RefreshCw className="spinner" size={16} />
              Building Context Graph...
            </>
          ) : "Build Knowledge Graph"}
        </button>

        {error && (
          <div style={{ marginTop: '1rem', color: 'var(--error)', fontSize: '0.9rem' }}>
            {error}
          </div>
        )}

        {summary && (
          <div style={{
            marginTop: '1.5rem',
            padding: '1rem',
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid var(--success)',
            color: 'var(--success)',
            borderRadius: 'var(--radius-sm)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.9rem'
          }}>
            <CheckCircle size={18} />
            Graph ready in {summary.graph_store.toUpperCase()} mode.
          </div>
        )}
      </div>

      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
          <Network size={20} />
          Context Graph Preview
        </h2>

        {summary ? (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
              <div className="metric-card">
                <div style={{ fontSize: '0.75rem', color: 'var(--secondary-foreground)' }}>ENTITIES</div>
                <div className="metric-value">{summary.nodes_count}</div>
              </div>
              <div className="metric-card">
                <div style={{ fontSize: '0.75rem', color: 'var(--secondary-foreground)' }}>RELATIONS</div>
                <div className="metric-value">{summary.edges_count}</div>
              </div>
              <div className="metric-card">
                <div style={{ fontSize: '0.75rem', color: 'var(--secondary-foreground)' }}>MENTIONS</div>
                <div className="metric-value">{summary.chunk_links_count}</div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', overflowY: 'auto', maxHeight: '260px' }}>
              {summary.top_entities.map((entity) => (
                <div key={entity.id} style={{
                  background: 'var(--secondary)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.75rem'
                }}>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{entity.label}</div>
                  <div style={{ color: 'var(--muted-foreground)', fontSize: '0.8rem' }}>
                    {entity.mentions} mentions
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div style={{ color: 'var(--muted-foreground)', textAlign: 'center', fontSize: '0.9rem', padding: '2rem' }}>
            No context graph built yet. Build the graph after vector indexing to enable graph-first retrieval.
          </div>
        )}
      </div>
    </div>
  );
}
