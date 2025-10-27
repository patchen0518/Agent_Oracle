// Chat interface component for displaying message history
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import React, { useEffect, useRef } from 'react'
import Message from './Message'

const ChatInterface = ({ messages, isLoading }) => {
  const messagesEndRef = useRef(null)
  const chatContainerRef = useRef(null)

  // Auto-scroll to latest message when new messages are added
  useEffect(() => {
    if (messagesEndRef.current && messagesEndRef.current.scrollIntoView) {
      messagesEndRef.current.scrollIntoView({ 
        behavior: 'smooth',
        block: 'end'
      })
    }
  }, [messages, isLoading])

  // Handle scroll to bottom manually
  const scrollToBottom = () => {
    if (messagesEndRef.current && messagesEndRef.current.scrollIntoView) {
      messagesEndRef.current.scrollIntoView({ 
        behavior: 'smooth',
        block: 'end'
      })
    }
  }

  return (
    <div className="chat-interface">
      {/* Messages container */}
      <div 
        ref={chatContainerRef}
        className="messages-container"
      >
        {messages.length === 0 && !isLoading ? (
          <div className="empty-state">
            <div className="empty-content">
              <h3>Welcome to Oracle Chat</h3>
              <p>Start a conversation by typing a message below.</p>
            </div>
          </div>
        ) : (
          <div className="messages-list">
            {messages.map((message) => (
              <Message
                key={message.id}
                message={message}
              />
            ))}
            
            {/* Loading indicator */}
            {isLoading && (
              <div className="loading-message">
                <div className="message-bubble agent loading">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                  <div className="loading-text">Oracle is thinking...</div>
                </div>
              </div>
            )}
          </div>
        )}
        
        {/* Invisible element to scroll to */}
        <div ref={messagesEndRef} />
      </div>

      {/* Scroll to bottom button (appears when not at bottom) */}
      {messages.length > 3 && (
        <button
          onClick={scrollToBottom}
          className="scroll-to-bottom"
          aria-label="Scroll to bottom"
        >
          ↓
        </button>
      )}
    </div>
  )
}

export default ChatInterface