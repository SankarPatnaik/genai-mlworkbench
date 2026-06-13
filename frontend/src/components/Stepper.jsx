import React from 'react';

export default function Stepper({ steps, currentStep, setStep }) {
  return (
    <div className="stepper-nav">
      {steps.map((step, idx) => {
        const isActive = idx === currentStep;
        const isCompleted = idx < currentStep;
        
        let stepClass = "step-item";
        if (isActive) stepClass += " active";
        if (isCompleted) stepClass += " completed";
        
        return (
          <div 
            key={idx} 
            className={stepClass}
            onClick={() => setStep(idx)}
          >
            <div className="step-number">
              {isCompleted ? "✓" : idx + 1}
            </div>
            <div className="step-title">{step.title}</div>
          </div>
        );
      })}
    </div>
  );
}
