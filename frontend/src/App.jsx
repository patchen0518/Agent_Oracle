// Main App component for Oracle Chat
// Based on React v19+ documentation (Context 7 lookup: 2025-01-26)

import React, { useState, useEffect } from 'react'
import ChatInterface from './components/ChatInterface'
import MessageInput from './components/MessageInput'
import Message from './components/Message'
import { checkHealth } from './services/api'
import './App.css'

function App() {
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

  return (
    <div className="app">
      <header className="app-header">
        <h1>Oracle Chat</h1>
        <div className={`status ${backendStatus}`}>
          Backend: {backendStatus}
        </div>
      </header>
      
      <main className="app-main">
        <ChatInterface />
        <MessageInput />
        <Message />
      </main>
    </div>
  )
}

export default App
