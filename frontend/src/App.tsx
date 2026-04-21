import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, Brain, Database, ScrollText, Activity, Settings, LogOut } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import AgentChat from './pages/AgentChat'
import KnowledgeBase from './pages/KnowledgeBase'
import MemoryPage from './pages/MemoryPage'
import AuditLog from './pages/AuditLog'
import Metrics from './pages/Metrics'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <nav className="sidebar">
          <div className="sidebar-logo">🧠 Cortex</div>
          <div className="sidebar-nav">
            <NavLink to="/" end className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <LayoutDashboard size={16} /> Dashboard
            </NavLink>
            <NavLink to="/agent" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <Brain size={16} /> Agent
            </NavLink>
            <NavLink to="/knowledge" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <Database size={16} /> Knowledge Base
            </NavLink>
            <NavLink to="/memory" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <ScrollText size={16} /> Memory
            </NavLink>
            <NavLink to="/audit" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <ScrollText size={16} /> Audit Log
            </NavLink>
            <NavLink to="/metrics" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <Activity size={16} /> Metrics
            </NavLink>
          </div>
          <div className="nav-bottom">
            <button className="nav-item" style={{ background: 'none', border: 'none', cursor: 'pointer', width: '100%', textAlign: 'left' }}>
              <Settings size={16} /> Settings
            </button>
            <button className="nav-item" style={{ background: 'none', border: 'none', cursor: 'pointer', width: '100%', textAlign: 'left' }}>
              <LogOut size={16} /> Logout
            </button>
          </div>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/agent" element={<AgentChat />} />
            <Route path="/knowledge" element={<KnowledgeBase />} />
            <Route path="/memory" element={<MemoryPage />} />
            <Route path="/audit" element={<AuditLog />} />
            <Route path="/metrics" element={<Metrics />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}