// Custom hook for session management operations
// Handles session CRUD operations, state management, and error handling

import { useState, useCallback, useEffect } from 'react'
import { 
  createSession, 
  getSessions, 
  getSession, 
  updateSession, 
  deleteSession 
} from '../services/api.js'
import useErrorHandler from './useErrorHandler.js'

const useSessionManager = () => {
  const [sessions, setSessions] = useState([])
  const [activeSession, setActiveSession] = useState(null)
  const [loading, setLoading] = useState(false)
  const [initialized, setInitialized] = useState(false)
  
  const { error, handleError, clearError, retry, canRetry } = useErrorHandler()

  // Load all sessions from the server
  const loadSessions = useCallback(async () => {
    setLoading(true)
    clearError()
    
    try {
      const sessionList = await getSessions()
      setSessions(sessionList)
      
      // If no active session is set and we have sessions, set the first one as active
      if (!activeSession && sessionList.length > 0) {
        setActiveSession(sessionList[0])
      }
      
      return sessionList
    } catch (err) {
      handleError(err)
      return []
    } finally {
      setLoading(false)
    }
  }, [activeSession, handleError, clearError])

  // Initialize sessions on first load
  useEffect(() => {
    if (!initialized) {
      loadSessions().then(() => {
        setInitialized(true)
      })
    }
  }, [initialized, loadSessions])

  // Create a new session
  const createNewSession = useCallback(async (sessionData = {}) => {
    setLoading(true)
    clearError()
    
    try {
      const newSession = await createSession(sessionData)
      
      // Add to sessions list
      setSessions(prev => [newSession, ...prev])
      
      // Set as active session
      setActiveSession(newSession)
      
      return newSession
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setLoading(false)
    }
  }, [handleError, clearError])

  // Switch to a different session
  const switchSession = useCallback(async (sessionId) => {
    if (!sessionId) {
      handleError(new Error('Session ID is required'))
      return null
    }

    setLoading(true)
    clearError()
    
    try {
      // First check if session is already in our list
      const existingSession = sessions.find(s => s.id === sessionId)
      
      if (existingSession) {
        setActiveSession(existingSession)
        return existingSession
      }
      
      // If not in list, fetch from server
      const session = await getSession(sessionId)
      
      // Add to sessions list if not already there
      setSessions(prev => {
        const exists = prev.find(s => s.id === sessionId)
        if (exists) return prev
        return [session, ...prev]
      })
      
      setActiveSession(session)
      return session
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setLoading(false)
    }
  }, [sessions, handleError, clearError])

  // Update session metadata
  const updateSessionData = useCallback(async (sessionId, updates) => {
    if (!sessionId) {
      handleError(new Error('Session ID is required'))
      return null
    }

    setLoading(true)
    clearError()
    
    try {
      const updatedSession = await updateSession(sessionId, updates)
      
      // Update in sessions list
      setSessions(prev => 
        prev.map(session => 
          session.id === sessionId ? updatedSession : session
        )
      )
      
      // Update active session if it's the one being updated
      if (activeSession && activeSession.id === sessionId) {
        setActiveSession(updatedSession)
      }
      
      return updatedSession
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setLoading(false)
    }
  }, [activeSession, handleError, clearError])

  // Delete a session
  const deleteSessionById = useCallback(async (sessionId) => {
    if (!sessionId) {
      handleError(new Error('Session ID is required'))
      return false
    }

    setLoading(true)
    clearError()
    
    try {
      await deleteSession(sessionId)
      
      // Remove from sessions list
      setSessions(prev => prev.filter(session => session.id !== sessionId))
      
      // If deleted session was active, switch to another session or clear active
      if (activeSession && activeSession.id === sessionId) {
        const remainingSessions = sessions.filter(s => s.id !== sessionId)
        if (remainingSessions.length > 0) {
          setActiveSession(remainingSessions[0])
        } else {
          setActiveSession(null)
        }
      }
      
      return true
    } catch (err) {
      handleError(err)
      return false
    } finally {
      setLoading(false)
    }
  }, [sessions, activeSession, handleError, clearError])

  // Refresh current session data
  const refreshActiveSession = useCallback(async () => {
    if (!activeSession) return null

    setLoading(true)
    clearError()
    
    try {
      const refreshedSession = await getSession(activeSession.id)
      
      // Update in sessions list
      setSessions(prev => 
        prev.map(session => 
          session.id === activeSession.id ? refreshedSession : session
        )
      )
      
      setActiveSession(refreshedSession)
      return refreshedSession
    } catch (err) {
      handleError(err)
      return null
    } finally {
      setLoading(false)
    }
  }, [activeSession, handleError, clearError])

  // Retry last failed operation
  const retryLastOperation = useCallback(async () => {
    return await retry(loadSessions)
  }, [retry, loadSessions])

  return {
    // State
    sessions,
    activeSession,
    loading,
    initialized,
    error,
    canRetry,
    
    // Actions
    loadSessions,
    createNewSession,
    switchSession,
    updateSessionData,
    deleteSessionById,
    refreshActiveSession,
    retryLastOperation,
    clearError
  }
}

export default useSessionManager