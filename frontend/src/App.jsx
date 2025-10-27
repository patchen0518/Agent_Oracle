// Main App component for Oracle Chat
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import React, { useState, useEffect } from 'react'
import ChatInterface from './components/ChatInterface'
import MessageInput from './components/MessageInput'
import { checkHealth, postChatMessage } from './services/api'
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
  const [error, setError] = useState(null)
  const [backendStatus, setBackendStatus] = useState('checking')

  useEffect(() => {
    // Check backend health on app load
    const checkBackendHealth = async () => {
      try {
        await checkHealth()
        setBackendStatus('connected')
      } catch (error) {
        setBackendStatus('disconnected')
        console.error('Backend health check failed:', error.message)
      }
    }

    checkBackendHealth()
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
    setError(null)

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
      setError('Failed to send message. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  // Clear error state
  const clearError = () => setError(null)

  return (
    <ErrorBoundary>
      <div className="app">
        <header className="app-header">
          <h1>Oracle Chat</h1>
          <div className={`status ${backendStatus}`}>
            Backend: {backendStatus}
          </div>
        </header>
        
        <main className="app-main">
          <ChatInterface 
            messages={messages}
            isLoading={isLoading}
            error={error}
            onClearError={clearError}
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
