// Main App component for Oracle Chat
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import React, { useState, useEffect } from 'react'
import SessionLayout from './components/SessionLayout'
import ChatInterface from './components/ChatInterface'
import MessageInput from './components/MessageInput'
import ErrorDisplay from './components/ErrorDisplay'
import { 
  checkHealth, 
  getSessions, 
  createSession, 
  updateSession, 
  deleteSession, 
  sendSessionMessage, 
  getSessionMessages 
} from './services/api'
import useErrorHandler from './hooks/useErrorHandler'
import './App.css'

// Error Boundary component for handling unhandled errors
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    // Log error details for debugging
    console.error('Error caught by boundary:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <p>An unexpected error occurred. Please refresh the page to try again.</p>
          <button onClick={() => window.location.reload()}>
            Refresh Page
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

function App() {
  // Session state management
  const [sessions, setSessions] = useState([])
  const [activeSession, setActiveSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [backendStatus, setBackendStatus] = useState('checking')
  const [connectionError, setConnectionError] = useState(null)
  
  // Enhanced error handling
  const { 
    error, 
    errorType, 
    canRetry, 
    handleError, 
    clearError, 
    retry 
  } = useErrorHandler()

  useEffect(() => {
    // Check backend health and load sessions on app load
    const initializeApp = async () => {
      try {
        await checkHealth()
        setBackendStatus('connected')
        setConnectionError(null)
        
        // Load sessions after successful health check
        await loadSessions()
      } catch (error) {
        setBackendStatus('disconnected')
        setConnectionError('Backend server is not available')
        console.error('Backend health check failed:', error.message)
      }
    }

    initializeApp()
    
    // Set up periodic health checks
    const healthCheckInterval = setInterval(async () => {
      try {
        await checkHealth()
        setBackendStatus('connected')
        setConnectionError(null)
      } catch (error) {
        setBackendStatus('disconnected')
        setConnectionError('Backend server is not available')
        console.error('Backend health check failed:', error.message)
      }
    }, 30000) // Check every 30 seconds
    
    return () => clearInterval(healthCheckInterval)
  }, [])

  // Load all sessions
  const loadSessions = async () => {
    setSessionsLoading(true)
    try {
      const sessionsData = await getSessions()
      setSessions(sessionsData)
      
      // If no active session and sessions exist, select the first one
      if (!activeSession && sessionsData.length > 0) {
        setActiveSession(sessionsData[0])
      }
    } catch (error) {
      console.error('Failed to load sessions:', error)
      handleError(error)
    } finally {
      setSessionsLoading(false)
    }
  }

  // Load messages for a specific session
  const loadSessionMessages = async (sessionId) => {
    try {
      // Find the session to check message count first
      const session = sessions.find(s => s.id === sessionId)
      
      // If session has no messages, skip API call and set empty array immediately
      if (session && session.message_count === 0) {
        setMessages([])
        return
      }
      
      const messagesData = await getSessionMessages(sessionId)
      setMessages(messagesData)
    } catch (error) {
      console.error('Failed to load session messages:', error)
      handleError(error)
      setMessages([]) // Clear messages on error
    }
  }

  // Handle session selection
  const handleSessionSelect = async (sessionId) => {
    const session = sessions.find(s => s.id === sessionId)
    if (session) {
      setActiveSession(session)
      await loadSessionMessages(sessionId)
    }
  }

  // Handle session creation
  const handleSessionCreate = async (sessionData = {}) => {
    try {
      const newSession = await createSession(sessionData)
      setSessions(prev => [newSession, ...prev])
      setActiveSession(newSession)
      setMessages([]) // New session starts with empty messages
      return newSession
    } catch (error) {
      console.error('Failed to create session:', error)
      handleError(error)
      throw error
    }
  }

  // Handle session update
  const handleSessionUpdate = async (sessionId, updates) => {
    try {
      const updatedSession = await updateSession(sessionId, updates)
      setSessions(prev => prev.map(s => s.id === sessionId ? updatedSession : s))
      
      // Update active session if it's the one being updated
      if (activeSession?.id === sessionId) {
        setActiveSession(updatedSession)
      }
      
      return updatedSession
    } catch (error) {
      console.error('Failed to update session:', error)
      handleError(error)
      throw error
    }
  }

  // Handle session deletion
  const handleSessionDelete = async (sessionId) => {
    try {
      await deleteSession(sessionId)
      setSessions(prev => prev.filter(s => s.id !== sessionId))
      
      // If deleting active session, switch to another session or clear
      if (activeSession?.id === sessionId) {
        const remainingSessions = sessions.filter(s => s.id !== sessionId)
        if (remainingSessions.length > 0) {
          const nextSession = remainingSessions[0]
          setActiveSession(nextSession)
          await loadSessionMessages(nextSession.id)
        } else {
          setActiveSession(null)
          setMessages([])
        }
      }
    } catch (error) {
      console.error('Failed to delete session:', error)
      handleError(error)
      throw error
    }
  }

  // Handle sending a new message
  const handleSendMessage = async (messageText) => {
    if (!messageText.trim() || !activeSession) return

    // Create user message optimistically
    const userMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: messageText,
      timestamp: new Date(),
      session_id: activeSession.id
    }
    
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    clearError()

    try {
      // Send message to session-based endpoint
      const response = await sendSessionMessage(activeSession.id, messageText)
      
      // Replace temporary user message and add both real messages from response
      setMessages(prev => {
        // Remove the temporary user message and add both real messages
        const withoutTemp = prev.filter(msg => msg.id !== userMessage.id)
        return [...withoutTemp, response.user_message, response.assistant_message]
      })

      // Update session metadata from response
      setSessions(prev => prev.map(s => 
        s.id === activeSession.id 
          ? response.session
          : s
      ))
      
      // Update active session
      setActiveSession(response.session)

    } catch (err) {
      console.error('Failed to send message:', err)
      // Remove the optimistic user message on error
      setMessages(prev => prev.filter(msg => msg.id !== userMessage.id))
      handleError(err)
    } finally {
      setIsLoading(false)
    }
  }

  // Retry sending the last message
  const handleRetry = async () => {
    if (messages.length === 0 || !activeSession) return
    
    // Find the last user message
    const lastUserMessage = [...messages].reverse().find(msg => msg.role === 'user')
    if (lastUserMessage) {
      // Remove any messages after the last user message (in case of partial failure)
      const lastUserIndex = messages.findIndex(msg => msg.id === lastUserMessage.id)
      setMessages(prev => prev.slice(0, lastUserIndex + 1))
      
      // Retry with the enhanced retry mechanism
      await retry(() => handleSendMessage(lastUserMessage.content))
    }
  }

  // Reconnect to backend
  const handleReconnect = async () => {
    setBackendStatus('checking')
    try {
      await checkHealth()
      setBackendStatus('connected')
      setConnectionError(null)
    } catch (error) {
      setBackendStatus('disconnected')
      setConnectionError('Failed to reconnect to backend')
    }
  }

  return (
    <ErrorBoundary>
      <div className="app">
        <SessionLayout
          sessions={sessions}
          activeSession={activeSession}
          onSessionSelect={handleSessionSelect}
          onSessionCreate={handleSessionCreate}
          onSessionDelete={handleSessionDelete}
          onSessionUpdate={handleSessionUpdate}
          isLoading={sessionsLoading}
          backendStatus={backendStatus}
        >
          {/* Connection error display */}
          {connectionError && (
            <ErrorDisplay
              error={connectionError}
              type="network"
              onRetry={handleReconnect}
              onDismiss={() => setConnectionError(null)}
            />
          )}
          
          {/* Chat error display */}
          {error && (
            <ErrorDisplay
              error={error}
              type={errorType}
              onRetry={canRetry ? handleRetry : null}
              onDismiss={clearError}
            />
          )}
          
          <ChatInterface 
            sessionId={activeSession?.id}
            messages={messages}
            isLoading={isLoading}
            onLoadMessages={loadSessionMessages}
          />
          <MessageInput 
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            disabled={backendStatus !== 'connected' || !activeSession}
            placeholder={activeSession ? 'Type your message...' : 'Create or select a session to start chatting'}
          />
        </SessionLayout>
      </div>
    </ErrorBoundary>
  )
}

export default App
