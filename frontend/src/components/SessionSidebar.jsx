// Session sidebar component for managing chat sessions
// Based on React v19+ documentation

import { useState, useEffect } from 'react'
import './SessionSidebar.css'

const SessionSidebar = ({ 
  sessions = [], 
  activeSessionId, 
  onSessionSelect, 
  onSessionCreate, 
  onSessionDelete,
  isLoading = false,
  isCollapsed = false,
  onToggleCollapse
}) => {
  const [newSessionTitle, setNewSessionTitle] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)

  // Handle creating a new session
  const handleCreateSession = async (e) => {
    e.preventDefault()
    if (!newSessionTitle.trim() || isCreating) return

    setIsCreating(true)
    try {
      await onSessionCreate(newSessionTitle.trim())
      setNewSessionTitle('')
      setShowCreateForm(false)
    } catch (error) {
      console.error('Failed to create session:', error)
    } finally {
      setIsCreating(false)
    }
  }

  // Handle session deletion with confirmation
  const handleDeleteSession = async (sessionId, sessionTitle) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${sessionTitle}"? This action cannot be undone.`
    )
    
    if (confirmed) {
      try {
        await onSessionDelete(sessionId)
      } catch (error) {
        console.error('Failed to delete session:', error)
      }
    }
  }

  // Format timestamp for display
  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now - date
    const diffHours = diffMs / (1000 * 60 * 60)
    const diffDays = diffMs / (1000 * 60 * 60 * 24)

    if (diffHours < 1) {
      const diffMinutes = Math.floor(diffMs / (1000 * 60))
      return diffMinutes < 1 ? 'Just now' : `${diffMinutes}m ago`
    } else if (diffHours < 24) {
      return `${Math.floor(diffHours)}h ago`
    } else if (diffDays < 7) {
      return `${Math.floor(diffDays)}d ago`
    } else {
      return date.toLocaleDateString()
    }
  }

  return (
    <div className={`session-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Sidebar Header */}
      <div className="sidebar-header">
        <div className="sidebar-title">
          {!isCollapsed && <h2>Sessions</h2>}
        </div>
        <button
          className="collapse-toggle"
          onClick={onToggleCollapse}
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? '→' : '←'}
        </button>
      </div>

      {!isCollapsed && (
        <>
          {/* Create Session Section */}
          <div className="create-session-section">
            {!showCreateForm ? (
              <button
                className="new-session-btn"
                onClick={() => setShowCreateForm(true)}
                disabled={isLoading}
              >
                <span className="plus-icon">+</span>
                New Session
              </button>
            ) : (
              <form onSubmit={handleCreateSession} className="create-session-form">
                <input
                  type="text"
                  value={newSessionTitle}
                  onChange={(e) => setNewSessionTitle(e.target.value)}
                  placeholder="Session title..."
                  className="session-title-input"
                  maxLength={200}
                  autoFocus
                />
                <div className="form-actions">
                  <button
                    type="submit"
                    disabled={!newSessionTitle.trim() || isCreating}
                    className="create-btn"
                  >
                    {isCreating ? 'Creating...' : 'Create'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreateForm(false)
                      setNewSessionTitle('')
                    }}
                    className="cancel-btn"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Sessions List */}
          <div className="sessions-list">
            {isLoading ? (
              <div className="loading-sessions">
                <div className="loading-spinner"></div>
                <span>Loading sessions...</span>
              </div>
            ) : sessions.length === 0 ? (
              <div className="empty-sessions">
                <p>No sessions yet</p>
                <p className="empty-hint">Create your first session to get started</p>
              </div>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.id}
                  className={`session-item ${
                    session.id === activeSessionId ? 'active' : ''
                  }`}
                  onClick={() => onSessionSelect(session.id)}
                >
                  <div className="session-content">
                    <div className="session-title" title={session.title}>
                      {session.title}
                    </div>
                    <div className="session-meta">
                      <span className="message-count">
                        {session.message_count || 0} messages
                      </span>
                      <span className="last-activity">
                        {formatTimestamp(session.updated_at)}
                      </span>
                    </div>
                  </div>
                  <button
                    className="delete-session-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteSession(session.id, session.title)
                    }}
                    aria-label={`Delete session "${session.title}"`}
                    title="Delete session"
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default SessionSidebar