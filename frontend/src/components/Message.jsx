// Individual message component for displaying chat messages
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import React, { memo } from 'react'

const Message = memo(({ message }) => {
  const { role, content, timestamp } = message

  // Format timestamp for display
  const formatTimestamp = (date) => {
    if (!date) return ''
    
    const now = new Date()
    const messageDate = new Date(date)
    const diffInMinutes = Math.floor((now - messageDate) / (1000 * 60))
    
    if (diffInMinutes < 1) {
      return 'Just now'
    } else if (diffInMinutes < 60) {
      return `${diffInMinutes}m ago`
    } else if (diffInMinutes < 1440) { // Less than 24 hours
      const hours = Math.floor(diffInMinutes / 60)
      return `${hours}h ago`
    } else {
      // More than 24 hours, show date
      return messageDate.toLocaleDateString()
    }
  }

  // Format message content (preserve line breaks)
  const formatContent = (text) => {
    if (!text) return ''
    
    // Split by line breaks and create paragraphs
    const lines = text.split('\n')
    return lines.map((line, index) => (
      <React.Fragment key={index}>
        {line}
        {index < lines.length - 1 && <br />}
      </React.Fragment>
    ))
  }

  // Determine message type and styling
  const isUser = role === 'user'
  const isAgent = role === 'model'

  return (
    <div className={`message ${isUser ? 'user' : 'agent'}`}>
      <div className="message-container">
        {/* Message avatar/indicator */}
        <div className="message-avatar">
          {isUser ? (
            <div className="avatar user-avatar">
              <span>You</span>
            </div>
          ) : (
            <div className="avatar agent-avatar">
              <span>🤖</span>
            </div>
          )}
        </div>

        {/* Message content */}
        <div className="message-content">
          <div className="message-header">
            <span className="message-sender">
              {isUser ? 'You' : 'Oracle'}
            </span>
            {timestamp && (
              <span className="message-timestamp">
                {formatTimestamp(timestamp)}
              </span>
            )}
          </div>
          
          <div className="message-bubble">
            <div className="message-text">
              {formatContent(content)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
})

export default Message