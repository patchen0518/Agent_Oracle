// Main App component for Oracle Chat
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import React, { useState, useEffect } from 'react'
import ChatInterface from './components/ChatInterface'
import MessageInput from './components/MessageInput'
import ErrorDisplay from './components/ErrorDisplay'
import { checkHealth, postChatMessage } from './services/api'
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
  // Chat state management
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
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
    // Check backend health on app load
    const checkBackendHealth = async () => {
      try {
        await checkHealth()
        setBackendStatus('connected')
        setConnectionError(null)
      } catch (error) {
        setBackendStatus('disconnected')
        setConnectionError('Backend server is not available')
        console.error('Backend health check failed:', error.message)
      }
    }

    checkBackendHealth()
    
    // Set up periodic health checks
    const healthCheckInterval = setInterval(checkBackendHealth, 30000) // Check every 30 seconds
    
    return () => clearInterval(healthCheckInterval)
  }, [])

  // Handle sending a new message
  const handleSendMessage = async (messageText) => {
    if (!messageText.trim()) return

    // Add user message to conversation
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: messageText,
      timestamp: new Date()
    }
    
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    clearError()

    try {
      // Prepare conversation history for API
      const history = messages.map(msg => ({
        role: msg.role,
        parts: msg.content
      }))

      // Send message to backend
      const response = await postChatMessage({
        message: messageText,
        history
      })

      // Add agent response to conversation
      const agentMessage = {
        id: Date.now() + 1,
        role: 'model',
        content: response.response,
        timestamp: new Date()
      }

      setMessages(prev => [...prev, agentMessage])
    } catch (err) {
      console.error('Failed to send message:', err)
      handleError(err)
    } finally {
      setIsLoading(false)
    }
  }

  // Retry sending the last message
  const handleRetry = async () => {
    if (messages.length === 0) return
    
    // Find the last user message
    const lastUserMessage = [...messages].reverse().find(msg => msg.role === 'user')
    if (lastUserMessage) {
      // Remove any agent messages after the last user message
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
        <header className="app-header">
          <h1>Oracle</h1>
          <div className={`status ${backendStatus}`}>
            Backend: {backendStatus}
          </div>
        </header>
        
        <main className="app-main">
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
            messages={messages}
            isLoading={isLoading}
          />
          <MessageInput 
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            disabled={backendStatus !== 'connected'}
          />
        </main>
      </div>
    </ErrorBoundary>
  )
}

export default App
