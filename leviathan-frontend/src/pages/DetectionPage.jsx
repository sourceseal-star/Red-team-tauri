import React, { useState } from 'react';
import CameraDetection from '../components/widgets/CameraDetection';
import QuickScan from '../components/widgets/QuickScan';
import StatsWidget from '../components/widgets/StatsWidget';
import ThreatMap from '../components/widgets/ThreatMap';
import '../styles/widgets.css';

const DetectionPage = () => {
  const [selectedCamera, setSelectedCamera] = useState(null);

  return (
    <div className="page detection-page">
      <h1 className="text-2xl font-bold mb-4">🎯 Detección</h1>
      
      <div className="page-grid">
        <div className="page-section">
          <CameraDetection 
            onCameraSelect={setSelectedCamera} 
            initialNetwork="192.168.0.0/24"
          />
        </div>
        
        <div className="page-section">
          <QuickScan onResultSelect={(result) => setSelectedCamera(result)} />
        </div>
        
        <div className="page-section">
          <StatsWidget />
        </div>
        
        <div className="page-section full-width">
          <ThreatMap onMarkerSelect={(marker) => console.log('Marker selected:', marker)} />
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

export default DetectionPage;
