// Session layout component for managing responsive session interface
// Based on React v19+ documentation

import { useState, useEffect } from 'react'
import SessionSidebar from './SessionSidebar'
import SessionHeader from './SessionHeader'
import './SessionLayout.css'

const SessionLayout = ({ 
  sessions = [],
  activeSession,
  onSessionSelect,
  onSessionCreate,
  onSessionDelete,
  onSessionUpdate,
  isLoading = false,
  backendStatus = 'connected',
  children
}) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  // Detect mobile screen size
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth <= 768
      setIsMobile(mobile)
      
      // Auto-close sidebar on mobile when screen size changes
      if (mobile && isSidebarOpen) {
        setIsSidebarOpen(false)
      }
      
      // Reset collapsed state on desktop
      if (!mobile) {
        setIsSidebarCollapsed(false)
      }
    }

    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [isSidebarOpen])

  // Handle sidebar toggle
  const handleToggleSidebar = () => {
    if (isMobile) {
      setIsSidebarOpen(!isSidebarOpen)
    } else {
      setIsSidebarCollapsed(!isSidebarCollapsed)
    }
  }

  // Close sidebar when clicking outside on mobile
  const handleOverlayClick = () => {
    if (isMobile && isSidebarOpen) {
      setIsSidebarOpen(false)
    }
  }

  // Close sidebar when session is selected on mobile
  const handleSessionSelect = (sessionId) => {
    onSessionSelect(sessionId)
    if (isMobile) {
      setIsSidebarOpen(false)
    }
  }

  // Handle escape key to close sidebar on mobile
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isMobile && isSidebarOpen) {
        setIsSidebarOpen(false)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isMobile, isSidebarOpen])

  // Prevent body scroll when sidebar is open on mobile
  useEffect(() => {
    if (isMobile && isSidebarOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }

    return () => {
      document.body.style.overflow = ''
    }
  }, [isMobile, isSidebarOpen])

  return (
    <div className={`session-layout ${isMobile ? 'mobile' : 'desktop'}`}>
      {/* Mobile overlay */}
      {isMobile && isSidebarOpen && (
        <div 
          className="sidebar-overlay"
          onClick={handleOverlayClick}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <div className={`sidebar-container ${
        isMobile ? (isSidebarOpen ? 'open' : 'closed') : 
        (isSidebarCollapsed ? 'collapsed' : 'expanded')
      }`}>
        <SessionSidebar
          sessions={sessions}
          activeSessionId={activeSession?.id}
          onSessionSelect={handleSessionSelect}
          onSessionCreate={onSessionCreate}
          onSessionDelete={onSessionDelete}
          isLoading={isLoading}
          isCollapsed={!isMobile && isSidebarCollapsed}
          onToggleCollapse={handleToggleSidebar}
        />
      </div>

      {/* Main content area */}
      <div className="main-content">
        <SessionHeader
          session={activeSession}
          onSessionUpdate={onSessionUpdate}
          onSessionDelete={onSessionDelete}
          onToggleSidebar={handleToggleSidebar}
          backendStatus={backendStatus}
        />
        
        <div className="content-area">
          {children}
        </div>
      </div>

      {/* Mobile sidebar indicator */}
      {isMobile && sessions.length > 0 && !isSidebarOpen && (
        <button
          className="mobile-sidebar-indicator"
          onClick={handleToggleSidebar}
          aria-label="Open sessions"
        >
          <span className="session-count">{sessions.length}</span>
          <span className="indicator-text">Sessions</span>
        </button>
      )}
    </div>
  )
}

export default SessionLayout