import React, { useEffect, useState } from 'react';
import { Cpu, HelpCircle } from 'lucide-react';

export default function AgentStep({ data, updateData }) {
  const [framework, setFramework] = useState(data.framework || 'direct');
  const [systemInstruction, setSystemInstruction] = useState(data.systemInstruction || 
`You are a helpful customer support agent. Answer questions using ONLY the context below. 

CONTEXT:
{{CONTEXT}}

If the context does not contain the answer, politely respond that the information is not present in the reference documents.`);
  const [llmModel, setLlmModel] = useState(data.llmModel || 'local-preview');
  const [temperature, setTemperature] = useState(data.temperature || 0.7);
  const [topK, setTopK] = useState(data.topK || 3);

  useEffect(() => {
    updateData({
      framework,
      systemInstruction,
      llmModel,
      temperature,
      topK
    });
  }, [framework, systemInstruction, llmModel, temperature, topK]);

  return (
    <div className="step-layout-grid">
      <div className="glass-panel">
        <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
          <Cpu size={20} />
          Agent Framework & Prompt Engine
        </h2>

        <div className="form-group">
          <label>Agentic Orchestration Framework</label>
          <select value={framework} onChange={(e) => setFramework(e.target.value)}>
            <option value="direct">Direct RAG Preview (Local Mock Runtime)</option>
            <option value="langgraph">LangGraph (Stateful Node DAG)</option>
            <option value="crewai">CrewAI (Multi-Agent Task Collaboration)</option>
            <option value="google_sdk">Google SDK Adapter (Requires backend integration)</option>
          </select>
        </div>

        <div className="form-group">
          <label>LLM Router Engine</label>
          <select value={llmModel} onChange={(e) => setLlmModel(e.target.value)}>
            <option value="local-preview">Local Preview Runtime</option>
            <option value="gemini-1.5-pro">Gemini Adapter (Requires provider wiring)</option>
            <option value="gpt-4o-mini">OpenAI Adapter (Requires provider wiring)</option>
          </select>
        </div>

        <div className="form-group">
          <label>Top-K Search Matches: {topK} Chunks</label>
          <input 
            type="range" 
            min={1} 
            max={10} 
            step={1}
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label>Temperature: {temperature}</label>
          <input 
            type="range" 
            min={0.0} 
            max={1.5} 
            step={0.1}
            value={temperature}
            onChange={(e) => setTemperature(parseFloat(e.target.value))}
          />
        </div>
      </div>

      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ marginBottom: '1rem', fontSize: '1.25rem' }}>System Instructions</h2>
        <p style={{ color: 'var(--secondary-foreground)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
          Define instructions. Ensure you inject the <code>{"{{CONTEXT}}"}</code> tag where retrieved vector matches are loaded.
        </p>

        <div className="form-group" style={{ flex: 1 }}>
          <textarea
            style={{ 
              flex: 1, 
              minHeight: '220px', 
              fontFamily: 'monospace', 
              fontSize: '0.85rem',
              lineHeight: 1.5,
              resize: 'none'
            }}
            value={systemInstruction}
            onChange={(e) => setSystemInstruction(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
