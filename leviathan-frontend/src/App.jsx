import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { LeviathanProvider } from './hooks/useLeviathan';
import { WebSocketProvider } from './hooks/useWebSocket';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import DetectionPage from './pages/DetectionPage';
import AnalysisPage from './pages/AnalysisPage';
import ExploitPage from './pages/ExploitPage';
import ReportsPage from './pages/ReportsPage';
import './styles/index.css';
import './styles/theme.css';

const App = () => {
  return (
    <LeviathanProvider>
      <WebSocketProvider>
        <Router>
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/detection" element={<DetectionPage />} />
              <Route path="/analysis" element={<AnalysisPage />} />
              <Route path="/exploit" element={<ExploitPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        </Router>
      </WebSocketProvider>
    </LeviathanProvider>
  );
};

export default App;
