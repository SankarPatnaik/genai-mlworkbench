import React, { useState } from 'react';
import { Upload, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import { apiHeaders, apiUrl, parseApiError } from '../api';

export default function UploadStep({ data, updateData, onNext }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = async (selectedFile) => {
    setFile(selectedFile);
    setLoading(true);
    setError(null);
    setSuccess(false);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch(apiUrl("/api/v1/upload"), {
        method: "POST",
        headers: apiHeaders(),
        body: formData,
      });

      if (!response.ok) {
        throw new Error(await parseApiError(response, "Failed to upload file"));
      }

      const result = await response.json();
      updateData({
        documentId: result.document_id,
        filename: result.filename,
        text: result.text_preview,
        totalCharacters: result.total_characters,
        rawText: result.text_preview // Simple fallback context limit
      });
      setSuccess(true);
    } catch (err) {
      setError(err.message || "An error occurred during upload.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="step-layout-grid">
      <div className="glass-panel">
        <h2 style={{ marginBottom: '1rem', fontSize: '1.25rem' }}>Upload Document</h2>
        <p style={{ color: 'var(--secondary-foreground)', marginBottom: '2rem' }}>
          Upload PDF, Markdown, Text, HTML, or CSV files and extract clean text for retrieval.
        </p>

        <div 
          className="upload-drop-zone"
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input').click()}
        >
          <input 
            type="file" 
            id="file-input" 
            style={{ display: 'none' }} 
            onChange={handleFileChange}
            accept=".pdf,.html,.md,.txt,.csv"
          />
          <Upload size={40} className="primary" style={{ color: 'var(--primary)' }} />
          <div>
            <span style={{ fontWeight: 600 }}>Drag & Drop</span> or click to upload
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--muted-foreground)' }}>
            PDF, HTML, MD, TXT, CSV (Max 50MB)
          </span>
        </div>

        {file && (
          <div style={{ marginTop: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <FileText size={20} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 500 }}>{file.name}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--secondary-foreground)' }}>
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </div>
            </div>
            {loading && <div className="spinner"></div>}
            {success && <CheckCircle2 style={{ color: 'var(--success)' }} />}
            {error && <AlertCircle style={{ color: 'var(--error)' }} />}
          </div>
        )}

        {error && (
          <div style={{ marginTop: '1rem', color: 'var(--error)', fontSize: '0.9rem' }}>
            {error}
          </div>
        )}
      </div>

      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ marginBottom: '1rem', fontSize: '1.25rem' }}>PDF Conversion Viewer</h2>
        <p style={{ color: 'var(--secondary-foreground)', marginBottom: '1.5rem' }}>
          Real-time standardized PDF output text layout.
        </p>
        
        <div style={{ 
          flex: 1, 
          background: 'rgba(0, 0, 0, 0.2)', 
          borderRadius: 'var(--radius-md)', 
          padding: '1.5rem',
          border: '1px solid var(--border)',
          fontFamily: 'monospace',
          fontSize: '0.85rem',
          whiteSpace: 'pre-wrap',
          overflowY: 'auto',
          maxHeight: '350px'
        }}>
          {data.text ? data.text : "No document uploaded yet. Extracted text will appear here."}
        </div>
      </div>
    </div>
  );
}
