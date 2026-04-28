import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Database,
  FileText,
  ScrollText,
  Settings,
  LogOut,
  AlertTriangle,
  Box,
  CheckSquare,
  Network,
} from 'lucide-react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import Dashboard from './pages/Dashboard'
import AssetsPage from './pages/AssetsPage'
import RequirementsPage from './pages/RequirementsPage'
import SoupPage from './pages/SoupPage'
import TestRecordsPage from './pages/TestRecordsPage'
import RTMPage from './pages/RTMPage'
import AuditLog from './pages/AuditLog'
import LoginPage from './pages/LoginPage'
import './App.css'

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth()
  if (loading) return <div className="login-bg"><div className="login-card"><p className="text-muted text-sm">Loading…</p></div></div>
  if (!isAuthenticated) return <LoginPage />
  return <>{children}</>
}

function Sidebar() {
  const { logout, user } = useAuth()
  return (
    <nav className="sidebar">
      <div className="sidebar-logo">🚄 Cortex</div>
      <div className="sidebar-nav">
        <NavLink to="/" end className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <LayoutDashboard size={16} /> Dashboard
        </NavLink>
        <NavLink to="/assets" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <Box size={16} /> Assets
        </NavLink>
        <NavLink to="/requirements" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <FileText size={16} /> Requirements
        </NavLink>
        <NavLink to="/soups" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <Database size={16} /> SOUPs
        </NavLink>
        <NavLink to="/tests" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <CheckSquare size={16} /> Test Records
        </NavLink>
        <NavLink to="/rtm" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <Network size={16} /> RTM
        </NavLink>
        <NavLink to="/incidents" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <AlertTriangle size={16} /> Incidents
        </NavLink>
        <NavLink to="/audit" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <ScrollText size={16} /> Audit Log
        </NavLink>
      </div>
      <div className="nav-bottom">
        <div className="nav-user-info">
          <span className="text-muted text-sm">{user?.role?.replace('_', ' ')}</span>
        </div>
        <button className="nav-item" style={{ background: 'none', border: 'none', cursor: 'pointer', width: '100%', textAlign: 'left' }}>
          <Settings size={16} /> Settings
        </button>
        <button className="nav-item" onClick={logout} style={{ background: 'none', border: 'none', cursor: 'pointer', width: '100%', textAlign: 'left', color: '#ef5350' }}>
          <LogOut size={16} /> Logout
        </button>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/*" element={
            <ProtectedLayout>
              <div className="app-layout">
                <Sidebar />
                <main className="main-content">
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/assets" element={<AssetsPage />} />
                    <Route path="/requirements" element={<RequirementsPage />} />
                    <Route path="/soups" element={<SoupPage />} />
                    <Route path="/tests" element={<TestRecordsPage />} />
                    <Route path="/rtm" element={<RTMPage />} />
                    <Route path="/audit" element={<AuditLog />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </main>
              </div>
            </ProtectedLayout>
          } />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
