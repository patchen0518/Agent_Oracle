// Chat interface component for displaying message history
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import React, { useEffect, useRef, useState, useCallback, memo } from 'react'
import Message from './Message'

const ChatInterface = memo(({ messages, isLoading }) => {
  const messagesEndRef = useRef(null)
  const chatContainerRef = useRef(null)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const [isUserScrolling, setIsUserScrolling] = useState(false)

  // Auto-scroll to latest message when new messages are added (only if user isn't scrolling)
  useEffect(() => {
    if (!isUserScrolling && messagesEndRef.current && messagesEndRef.current.scrollIntoView) {
      messagesEndRef.current.scrollIntoView({ 
        behavior: 'smooth',
        block: 'end'
      })
    }
  }, [messages, isLoading, isUserScrolling])

  // Handle scroll events to show/hide scroll button and detect user scrolling
  const handleScroll = useCallback(() => {
    if (!chatContainerRef.current) return

    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50 // 50px threshold
    
    setShowScrollButton(!isAtBottom && messages.length > 3)
    
    // Detect if user is actively scrolling
    setIsUserScrolling(!isAtBottom)
    
    // Clear user scrolling flag after a delay
    clearTimeout(handleScroll.timeoutId)
    handleScroll.timeoutId = setTimeout(() => {
      setIsUserScrolling(false)
    }, 1000)
  }, [messages.length])

  // Add scroll listener
  useEffect(() => {
    const container = chatContainerRef.current
    if (container) {
      container.addEventListener('scroll', handleScroll, { passive: true })
      return () => container.removeEventListener('scroll', handleScroll)
    }
  }, [handleScroll])

  // Handle scroll to bottom manually
  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current && messagesEndRef.current.scrollIntoView) {
      messagesEndRef.current.scrollIntoView({ 
        behavior: 'smooth',
        block: 'end'
      })
      setIsUserScrolling(false)
    }
  }, [])

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
      {showScrollButton && (
        <button
          onClick={scrollToBottom}
          className="scroll-to-bottom"
          aria-label="Scroll to bottom"
        >
          ↓ New messages
        </button>
      )}
    </div>
  )
})

export default ChatInterface