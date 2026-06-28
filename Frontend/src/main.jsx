import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import './globals.css';
import ChatPage from './pages/ChatPage';
import LoanAssessmentPage from './pages/LoanAssessmentPage';
import CollectionsAgentPage from './pages/CollectionsAgentPage';
import AppShell from './components/control/AppShell';
import ControlTower from './pages/control/ControlTower';
import AgentRegistry from './pages/control/AgentRegistry';
import RunConsole from './pages/control/RunConsole';
import Observability from './pages/control/Observability';
import PolicyGuardrails from './pages/control/PolicyGuardrails';
import KillSwitchDegradation from './pages/control/KillSwitchDegradation';
import AuditLogs from './pages/control/AuditLogs';
import AgentOnboarding from './pages/control/AgentOnboarding';
import UsageCost from './pages/control/UsageCost';
import AgenticPrimitives from './pages/control/AgenticPrimitives';
import RagQuality from './pages/control/RagQuality';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<Navigate to="/control/tower" replace />} />
          <Route path="control/tower" element={<ControlTower />} />
          <Route path="control/agents" element={<AgentRegistry />} />
          <Route path="control/run-console" element={<RunConsole />} />
          <Route path="control/observability" element={<Observability />} />
          <Route path="control/policy-guardrails" element={<PolicyGuardrails />} />
          <Route path="control/kill-switch" element={<KillSwitchDegradation />} />
          <Route path="control/audit-logs" element={<AuditLogs />} />
          <Route path="control/onboarding" element={<AgentOnboarding />} />
          <Route path="control/usage-cost" element={<UsageCost />} />
          <Route path="control/primitives" element={<AgenticPrimitives />} />
          <Route path="control/rag-quality" element={<RagQuality />} />
          <Route path="dashboard" element={<Navigate to="/control/tower" replace />} />
        </Route>
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/loan-assessment" element={<LoanAssessmentPage />} />
        <Route path="/collections" element={<CollectionsAgentPage />} />
        <Route path="*" element={<Navigate to="/control/tower" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);