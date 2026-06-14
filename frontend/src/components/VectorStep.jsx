import React, { useState } from 'react';
import { Database, CheckCircle, RefreshCw } from 'lucide-react';
import { apiHeaders, apiUrl, parseApiError } from '../api';

const INDEX_NAME_PATTERN = /^[A-Za-z][A-Za-z0-9_-]{2,62}$/;

export default function VectorStep({ data, updateData }) {
  const [vectorDb, setVectorDb] = useState(data.vectorDb || 'chroma');
  const [indexName, setIndexName] = useState(data.indexName || 'workbench-index');
  const [embeddingModel, setEmbeddingModel] = useState(data.embeddingModel || 'default');
  
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);

  const triggerIndexing = async () => {
    if (!data.chunks || data.chunks.length === 0) {
      setError("Please generate chunk partitions in Step 2 first.");
      return;
    }
    if (!INDEX_NAME_PATTERN.test(indexName)) {
      setError("Index names must start with a letter and use only letters, numbers, hyphens, or underscores.");
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await fetch(apiUrl("/api/v1/embed"), {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          document_id: data.documentId,
          vector_db: vectorDb,
          index_name: indexName,
          embedding_model: embeddingModel,
          chunks: data.chunks
        }),
      });

      if (!response.ok) {
        throw new Error(await parseApiError(response, "Failed to index chunks into Vector Database"));
      }

      const result = await response.json();
      updateData({
        vectorDb,
        indexName,
        embeddingModel,
        indexed: true
      });
      setSuccess(true);
    } catch (err) {
      setError(err.message || "An error occurred during embedding generation.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="step-layout-grid">
      <div className="glass-panel">
        <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
          <Database size={20} />
          Vector Database Index Configuration
        </h2>

        <div className="form-group">
          <label>Target Vector Database</label>
          <select value={vectorDb} onChange={(e) => setVectorDb(e.target.value)}>
            <option value="chroma">ChromaDB (Local One-Click)</option>
            <option value="qdrant">Qdrant Cloud/Local</option>
            <option value="postgres">PostgreSQL (pgvector Extension)</option>
          </select>
        </div>

        <div className="form-group">
          <label>Index / Collection Name</label>
          <input 
            type="text" 
            value={indexName}
            onChange={(e) => setIndexName(e.target.value)}
            placeholder="e.g. corporate-policies"
            pattern="[A-Za-z][A-Za-z0-9_-]{2,62}"
          />
        </div>

        <div className="form-group">
          <label>Embedding Model</label>
          <select value={embeddingModel} onChange={(e) => setEmbeddingModel(e.target.value)}>
            <option value="default">Local MiniLM-L6 (Default - Free Offline)</option>
          </select>
          <small style={{ color: 'var(--muted-foreground)' }}>
            Hosted embedding providers should be enabled after tenant billing, key vaulting and rate limits are in place.
          </small>
        </div>

        <button 
          className="btn btn-primary"
          style={{ width: '100%', marginTop: '1.5rem' }}
          onClick={triggerIndexing}
          disabled={loading || !data.chunks}
        >
          {loading ? (
            <>
              <RefreshCw className="spinner" size={16} />
              Generating & Indexing Embeddings...
            </>
          ) : "Embed & Index Chunks"}
        </button>

        {error && (
          <div style={{ marginTop: '1rem', color: 'var(--error)', fontSize: '0.9rem' }}>
            {error}
          </div>
        )}

        {success && (
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
            Successfully indexed {data.chunks.length} chunks into {vectorDb.toUpperCase()} [{indexName}].
          </div>
        )}
      </div>

      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: '1rem', textAlign: 'center' }}>
        <Database size={60} style={{ color: 'var(--primary)', opacity: 0.8 }} />
        <h3 style={{ fontSize: '1.15rem' }}>Vector Dimension Mapping</h3>
        <p style={{ color: 'var(--secondary-foreground)', fontSize: '0.9rem', maxWidth: '300px' }}>
          Embedding model will output standard vectors that are populated into isolated namespaces.
        </p>
        <div style={{ marginTop: '1rem', display: 'flex', gap: '2rem' }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--muted-foreground)' }}>DIMENSION</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{embeddingModel === 'default' ? '384' : embeddingModel === 'gemini' ? '768' : '1536'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--muted-foreground)' }}>METRIC</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>Cosine</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--muted-foreground)' }}>TOTAL VECTORS</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{data.chunks ? data.chunks.length : '0'}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
