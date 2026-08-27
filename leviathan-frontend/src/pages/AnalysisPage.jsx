import React, { useState } from 'react';
import AIAnalysis from '../components/widgets/AIAnalysis';
import ThreatMap from '../components/widgets/ThreatMap';
import StatsWidget from '../components/widgets/StatsWidget';
import AlertCenter from '../components/widgets/AlertCenter';
import '../styles/widgets.css';

const AnalysisPage = () => {
  const [selectedAlert, setSelectedAlert] = useState(null);

  return (
    <div className="page analysis-page">
      <h1 className="text-2xl font-bold mb-4">🔬 Análisis</h1>
      
      <div className="page-grid">
        <div className="page-section">
          <AIAnalysis onAnalysisComplete={(result) => console.log('Analysis complete:', result)} />
        </div>
        
        <div className="page-section">
          <StatsWidget />
        </div>
        
        <div className="page-section full-width">
          <ThreatMap onMarkerSelect={(marker) => console.log('Marker selected:', marker)} />
        </div>
        
        <div className="page-section">
          <AlertCenter onAlertSelect={setSelectedAlert} />
        </div>
      </div>

      <style jsx>{`
        .page {
          padding: var(--spacing-lg);
          animation: fadeIn 0.5s ease-out;
        }

        .page-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
          gap: var(--spacing-lg);
        }

        .page-section {
          min-height: 300px;
        }

        .page-section.full-width {
          grid-column: 1 / -1;
        }

        @media (max-width: 768px) {
          .page {
            padding: var(--spacing-sm);
          }
          
          .page-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};

export default AnalysisPage;
