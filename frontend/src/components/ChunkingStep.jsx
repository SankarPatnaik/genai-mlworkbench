import React, { useState } from 'react';
import { Settings, RefreshCw } from 'lucide-react';

export default function ChunkingStep({ data, updateData }) {
  const [method, setMethod] = useState(data.chunkMethod || 'recursive');
  const [chunkSize, setChunkSize] = useState(data.chunkSize || 500);
  const [chunkOverlap, setChunkOverlap] = useState(data.chunkOverlap || 50);
  const [similarityThreshold, setSimilarityThreshold] = useState(data.similarityThreshold || 0.85);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const triggerChunking = async () => {
    if (!data.documentId) {
      setError("Please upload a document first.");
      return;
    }
    
    setLoading(true);
    setError(null);

    const params = {};
    if (method === 'recursive' || method === 'fixed') {
      params.chunk_size = chunkSize;
    }
    if (method === 'recursive') {
      params.chunk_overlap = chunkOverlap;
    }
    if (method === 'semantic') {
      params.similarity_threshold = similarityThreshold;
    }

    try {
      const response = await fetch("http://localhost:8000/api/v1/chunk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: data.documentId,
          method,
          params
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to partition document chunks");
      }

      const result = await response.json();
      updateData({
        chunkMethod: method,
        chunkSize,
        chunkOverlap,
        similarityThreshold,
        chunks: result.chunks
      });
    } catch (err) {
      setError(err.message || "An error occurred during chunking.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="step-layout-grid">
      <div className="glass-panel">
        <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
          <Settings size={20} />
          Chunking Parameters
        </h2>

        <div className="form-group">
          <label>Chunking Method</label>
          <select value={method} onChange={(e) => setMethod(e.target.value)}>
            <option value="recursive">Recursive Character (Recommended)</option>
            <option value="fixed">Fixed-Size Chunking</option>
            <option value="semantic">Semantic Topic Shift</option>
            <option value="entire">Entire Document (Zero Chunking)</option>
          </select>
        </div>

        {(method === 'recursive' || method === 'fixed') && (
          <div className="form-group">
            <label>Chunk Size: {chunkSize} chars</label>
            <input 
              type="range" 
              min={100} 
              max={2000} 
              step={50}
              value={chunkSize}
              onChange={(e) => setChunkSize(parseInt(e.target.value))}
            />
          </div>
        )}

        {method === 'recursive' && (
          <div className="form-group">
            <label>Chunk Overlap: {chunkOverlap} chars</label>
            <input 
              type="range" 
              min={0} 
              max={500} 
              step={10}
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(parseInt(e.target.value))}
            />
          </div>
        )}

        {method === 'semantic' && (
          <div className="form-group">
            <label>Semantic Cosine Threshold: {similarityThreshold}</label>
            <input 
              type="range" 
              min={0.5} 
              max={0.99} 
              step={0.01}
              value={similarityThreshold}
              onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
            />
          </div>
        )}

        <button 
          className="btn btn-primary"
          style={{ width: '100%', marginTop: '1.5rem' }}
          onClick={triggerChunking}
          disabled={loading || !data.documentId}
        >
          {loading ? (
            <>
              <RefreshCw className="spinner" size={16} />
              Partitioning...
            </>
          ) : "Apply Chunking Strategy"}
        </button>

        {error && (
          <div style={{ marginTop: '1rem', color: 'var(--error)', fontSize: '0.9rem' }}>
            {error}
          </div>
        )}
      </div>

      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ marginBottom: '1rem', fontSize: '1.25rem' }}>Visual Chunk Inspector</h2>
        <p style={{ color: 'var(--secondary-foreground)', marginBottom: '1.5rem' }}>
          Inspect partitions. Colors represent sequential boundaries.
        </p>

        <div className="chunk-viewer">
          {data.chunks && data.chunks.length > 0 ? (
            data.chunks.map((chunk, idx) => {
              // Alternate translucent background colors for visual highlights
              const colors = [
                'rgba(99, 102, 241, 0.15)', // Indigo
                'rgba(168, 85, 247, 0.15)', // Purple
                'rgba(16, 185, 129, 0.15)', // Green
                'rgba(245, 158, 11, 0.15)'   // Orange
              ];
              const borderColors = [
                'rgba(99, 102, 241, 0.3)',
                'rgba(168, 85, 247, 0.3)',
                'rgba(16, 185, 129, 0.3)',
                'rgba(245, 158, 11, 0.3)'
              ];
              const cIdx = idx % colors.length;

              return (
                <div 
                  key={idx} 
                  className="chunk-card"
                  style={{
                    backgroundColor: colors[cIdx],
                    borderColor: borderColors[cIdx]
                  }}
                >
                  <div className="chunk-meta">
                    <span>CHUNK #{chunk.index}</span>
                    <span>{chunk.char_count} Chars | ~{chunk.token_count} Tokens</span>
                  </div>
                  <div className="chunk-text">{chunk.text}</div>
                </div>
              );
            })
          ) : (
            <div style={{ color: 'var(--muted-foreground)', textAlign: 'center', padding: '2rem' }}>
              No chunks generated yet. Click "Apply Chunking Strategy" to visualize.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
