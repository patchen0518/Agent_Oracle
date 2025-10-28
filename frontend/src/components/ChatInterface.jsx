// Chat interface component for displaying message history
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import { useEffect, useRef, useState, useCallback, memo } from 'react'
import Message from './Message'

const ChatInterface = memo(({ messages, isLoading }) => {
  const messagesEndRef = useRef(null)
  const chatContainerRef = useRef(null)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const [isUserScrolling, setIsUserScrolling] = useState(false)

  // Auto-scroll to latest message when new messages are added (only if user is at bottom)
  useEffect(() => {
    // Only auto-scroll if user is at the bottom (not scrolled up)
    if (!isUserScrolling && messagesEndRef.current) {
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

    // More reliable scroll detection using percentage-based calculation
    const scrollPercentage = (scrollTop + clientHeight) / scrollHeight
    const isAtBottom = scrollPercentage > 0.95 // 95% threshold (more lenient)

    // Alternative: Also check with pixel threshold for very small content
    const pixelThreshold = scrollHeight - scrollTop - clientHeight < 10 // 10px threshold (more lenient)
    const isAtBottomFinal = isAtBottom || pixelThreshold

    // Show button when not at bottom and have enough messages
    const shouldShowButton = !isAtBottomFinal && messages.length > 2
    setShowScrollButton(shouldShowButton)

    // Only set user scrolling to false when actually at bottom
    // Don't use timeout - let user control when they want to see new messages
    setIsUserScrolling(!isAtBottomFinal)
  }, [messages.length])

  // Add scroll listener
  useEffect(() => {
    const container = chatContainerRef.current
    if (container) {
      container.addEventListener('scroll', handleScroll, { passive: true })
      return () => container.removeEventListener('scroll', handleScroll)
    }
  }, [handleScroll])

  // Check scroll position when messages change
  useEffect(() => {
    if (chatContainerRef.current) {
      // Small delay to ensure DOM is updated
      setTimeout(() => {
        handleScroll()
      }, 100)
    }
  }, [messages, handleScroll])

  // Handle scroll to bottom manually
  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'end'
      })
      // Reset user scrolling state so auto-scroll resumes
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
              <h3>This is Oracle</h3>
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