import React, { useState, useEffect } from 'react';
import Stepper from './components/Stepper';
import UploadStep from './components/UploadStep';
import ChunkingStep from './components/ChunkingStep';
import VectorStep from './components/VectorStep';
import AgentStep from './components/AgentStep';
import PlaygroundStep from './components/PlaygroundStep';
import DeployStep from './components/DeployStep';

export default function App() {
  const [currentStep, setCurrentStep] = useState(0);
  const [data, setData] = useState({
    documentId: null,
    filename: null,
    text: null,
    totalCharacters: 0,
    chunks: [],
    vectorDb: 'chroma',
    indexName: 'workbench-index',
    embeddingModel: 'default',
    framework: 'google_sdk',
    systemInstruction: '',
    llmModel: 'gemini-3.5-flash',
    temperature: 0.7,
    topK: 3,
    indexed: false
  });

  const [apiStatus, setApiStatus] = useState(null);

  useEffect(() => {
    // Perform initial backend health check
    fetch("http://localhost:8000/api/v1/status")
      .then(res => res.json())
      .then(status => setApiStatus(status))
      .catch(() => setApiStatus(null));
  }, []);

  const updateData = (newData) => {
    setData(prev => ({ ...prev, ...newData }));
  };

  const steps = [
    { title: "Upload & Convert" },
    { title: "Chunking Settings" },
    { title: "Vector Store" },
    { title: "LLM & Prompts" },
    { title: "Playground & Costs" },
    { title: "Deploy & Integrate" }
  ];

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return <UploadStep data={data} updateData={updateData} onNext={handleNext} />;
      case 1:
        return <ChunkingStep data={data} updateData={updateData} />;
      case 2:
        return <VectorStep data={data} updateData={updateData} />;
      case 3:
        return <AgentStep data={data} updateData={updateData} />;
      case 4:
        return <PlaygroundStep data={data} updateData={updateData} />;
      case 5:
        return <DeployStep data={data} updateData={updateData} />;
      default:
        return <div>Unknown Step</div>;
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <div>
          <h1>GenAI Workbench</h1>
          <p>Low-Code / No-Code Agentic AI & Cost-Effective RAG Orchestration Panel</p>
        </div>
        
        {/* API Integration Diagnostics Indicator */}
        <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.8rem' }}>
          {apiStatus ? (
            <>
              <span style={{ 
                color: apiStatus.s3 === 'connected' ? 'var(--success)' : 'var(--error)', 
                background: 'rgba(255, 255, 255, 0.05)', 
                padding: '0.25rem 0.5rem', 
                borderRadius: 'var(--radius-sm)' 
              }}>
                S3: {apiStatus.s3}
              </span>
              <span style={{ 
                color: apiStatus.chroma === 'connected' ? 'var(--success)' : 'var(--muted-foreground)', 
                background: 'rgba(255, 255, 255, 0.05)', 
                padding: '0.25rem 0.5rem', 
                borderRadius: 'var(--radius-sm)' 
              }}>
                Chroma: {apiStatus.chroma}
              </span>
              <span style={{ 
                color: apiStatus.qdrant === 'connected' ? 'var(--success)' : 'var(--muted-foreground)', 
                background: 'rgba(255, 255, 255, 0.05)', 
                padding: '0.25rem 0.5rem', 
                borderRadius: 'var(--radius-sm)' 
              }}>
                Qdrant: {apiStatus.qdrant}
              </span>
              <span style={{ 
                color: apiStatus.postgres === 'connected' ? 'var(--success)' : 'var(--muted-foreground)', 
                background: 'rgba(255, 255, 255, 0.05)', 
                padding: '0.25rem 0.5rem', 
                borderRadius: 'var(--radius-sm)' 
              }}>
                PGVector: {apiStatus.postgres}
              </span>
            </>
          ) : (
            <span style={{ color: 'var(--error)' }}>Backend API Offline</span>
          )}
        </div>
      </header>

      {/* Top Stepper Navigation */}
      <Stepper 
        steps={steps} 
        currentStep={currentStep} 
        setStep={setCurrentStep} 
      />

      {/* Stepper active component content */}
      <main style={{ flex: 1 }}>
        {renderStepContent()}
      </main>

      {/* Stepper Footer Action Buttons */}
      <div className="step-actions">
        <button 
          className="btn btn-secondary" 
          onClick={handleBack} 
          disabled={currentStep === 0}
        >
          Back
        </button>
        
        <button 
          className="btn btn-primary" 
          onClick={handleNext} 
          disabled={
            currentStep === steps.length - 1 || 
            (currentStep === 0 && !data.documentId) ||
            (currentStep === 1 && data.chunks.length === 0) ||
            (currentStep === 2 && !data.indexed)
          }
        >
          {currentStep === steps.length - 2 ? "Finish Config" : "Continue"}
        </button>
      </div>
    </div>
  );
}
