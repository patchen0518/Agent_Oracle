// Session header component for displaying current session information
// Based on React v19+ documentation

import { useState, useRef, useEffect } from 'react'
import './SessionHeader.css'

const SessionHeader = ({ 
  session,
  onSessionUpdate,
  onSessionDelete,
  onToggleSidebar,
  backendStatus = 'connected'
}) => {
  const [isEditing, setIsEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [isUpdating, setIsUpdating] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const inputRef = useRef(null)

  // Initialize edit title when session changes
  useEffect(() => {
    if (session) {
      setEditTitle(session.title || '')
    }
  }, [session])

  // Focus input when editing starts
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditing])

  // Handle title editing
  const handleStartEdit = () => {
    if (!session) return
    setEditTitle(session.title || '')
    setIsEditing(true)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditTitle(session?.title || '')
  }

  const handleSaveEdit = async () => {
    if (!session || !editTitle.trim() || isUpdating) return
    
    const trimmedTitle = editTitle.trim()
    if (trimmedTitle === session.title) {
      setIsEditing(false)
      return
    }

    setIsUpdating(true)
    try {
      await onSessionUpdate(session.id, { title: trimmedTitle })
      setIsEditing(false)
    } catch (error) {
      console.error('Failed to update session title:', error)
      // Reset to original title on error
      setEditTitle(session.title || '')
    } finally {
      setIsUpdating(false)
    }
  }

  const handleBlur = async (e) => {
    // Don't save on blur if clicking cancel button
    if (e.relatedTarget?.title === 'Cancel editing') {
      return
    }
    
    // Only save on blur if the title has actually changed
    if (editTitle.trim() && editTitle.trim() !== session?.title) {
      await handleSaveEdit()
    } else {
      handleCancelEdit()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSaveEdit()
    } else if (e.key === 'Escape') {
      handleCancelEdit()
    }
  }

  // Handle session deletion
  const handleDeleteClick = () => {
    setShowDeleteConfirm(true)
  }

  const handleConfirmDelete = async () => {
    if (!session || isDeleting) return

    setIsDeleting(true)
    try {
      await onSessionDelete(session.id)
      setShowDeleteConfirm(false)
    } catch (error) {
      console.error('Failed to delete session:', error)
    } finally {
      setIsDeleting(false)
    }
  }

  const handleCancelDelete = () => {
    setShowDeleteConfirm(false)
  }

  // Format session metadata
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Unknown'
    
    try {
      // Handle both ISO string and Date object
      const date = new Date(timestamp)
      
      // Check if date is valid
      if (isNaN(date.getTime())) {
        console.warn('Invalid timestamp received:', timestamp)
        return 'Invalid Date'
      }
      
      return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit' 
      })
    } catch (error) {
      console.error('Error formatting timestamp:', error, timestamp)
      return 'Invalid Date'
    }
  }

  if (!session) {
    return (
      <header className="session-header no-session">
        <div className="header-left">
          <button
            className="sidebar-toggle"
            onClick={onToggleSidebar}
            aria-label="Toggle sidebar"
          >
            ☰
          </button>
          <div className="session-info">
            <h1 className="session-title">Oracle</h1>
            <p className="session-subtitle">Select a session to start chatting</p>
          </div>
        </div>
        <div className="header-right">
          <div className={`status ${backendStatus}`}>
            Backend: {backendStatus}
          </div>
        </div>
      </header>
    )
  }

  return (
    <header className="session-header">
      <div className="header-left">
        <button
          className="sidebar-toggle"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
        >
          ☰
        </button>
        
        <div className="session-info">
          {isEditing ? (
            <div className="title-edit-container">
              <input
                ref={inputRef}
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={handleKeyDown}
                onBlur={handleBlur}
                className="title-edit-input"
                maxLength={200}
                disabled={isUpdating}
              />
              <div className="edit-actions">
                <button
                  onClick={handleSaveEdit}
                  disabled={!editTitle.trim() || isUpdating}
                  className="save-btn"
                  title="Save title"
                >
                  {isUpdating ? '⏳' : '✓'}
                </button>
                <button
                  onClick={handleCancelEdit}
                  disabled={isUpdating}
                  className="cancel-btn"
                  title="Cancel editing"
                >
                  ✕
                </button>
              </div>
            </div>
          ) : (
            <div className="title-display-container">
              <h1 
                className="session-title clickable"
                onClick={handleStartEdit}
                title="Click to edit title"
              >
                {session.title}
                <span className="edit-icon">✏️</span>
              </h1>
            </div>
          )}
          
          <div className="session-metadata">
            <span className="message-count">
              {session.message_count || 0} messages
            </span>
            <span className="separator">•</span>
            <span className="created-date">
              Created {formatTimestamp(session.created_at)}
            </span>
            {session.updated_at !== session.created_at && (
              <>
                <span className="separator">•</span>
                <span className="last-activity">
                  Updated {formatTimestamp(session.updated_at)}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="header-right">
        <div className="session-controls">
          <button
            className="control-btn delete-btn"
            onClick={handleDeleteClick}
            title="Delete session"
            disabled={isDeleting}
          >
            🗑️
          </button>
        </div>
        
        <div className={`status ${backendStatus}`}>
          Backend: {backendStatus}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay" onClick={handleCancelDelete}>
          <div className="delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Delete Session</h3>
            </div>
            <div className="modal-body">
              <p>
                Are you sure you want to delete <strong>"{session.title}"</strong>?
              </p>
              <p className="warning-text">
                This will permanently delete all {session.message_count || 0} messages 
                in this session. This action cannot be undone.
              </p>
            </div>
            <div className="modal-actions">
              <button
                onClick={handleCancelDelete}
                disabled={isDeleting}
                className="cancel-modal-btn"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="delete-modal-btn"
              >
                {isDeleting ? 'Deleting...' : 'Delete Session'}
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  )
}

export default SessionHeader