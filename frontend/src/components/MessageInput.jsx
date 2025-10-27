// Message input component for chat interface
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import React, { useState } from 'react'

const MessageInput = ({ onSendMessage, isLoading, disabled }) => {
  const [message, setMessage] = useState('')
  const [validationError, setValidationError] = useState('')

  // Maximum message length
  const MAX_MESSAGE_LENGTH = 4000

  // Handle input change with validation
  const handleInputChange = (e) => {
    const value = e.target.value
    setMessage(value)
    
    // Clear validation error when user starts typing
    if (validationError) {
      setValidationError('')
    }

    // Check length validation
    if (value.length > MAX_MESSAGE_LENGTH) {
      setValidationError(`Message too long (${value.length}/${MAX_MESSAGE_LENGTH} characters)`)
    }
  }

  // Handle form submission
  const handleSubmit = (e) => {
    e.preventDefault()
    
    // Validate message
    const trimmedMessage = message.trim()
    
    if (!trimmedMessage) {
      setValidationError('Please enter a message')
      return
    }

    if (trimmedMessage.length > MAX_MESSAGE_LENGTH) {
      setValidationError(`Message too long (${trimmedMessage.length}/${MAX_MESSAGE_LENGTH} characters)`)
      return
    }

    // Clear validation error and send message
    setValidationError('')
    onSendMessage(trimmedMessage)
    
    // Clear input after sending
    setMessage('')
  }

  // Handle Enter key press (with Shift+Enter for new lines)
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const isDisabled = disabled || isLoading || message.length > MAX_MESSAGE_LENGTH

  return (
    <div className="message-input">
      <form onSubmit={handleSubmit} className="message-form">
        <div className="input-container">
          <textarea
            value={message}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            placeholder={disabled ? "Backend not connected..." : "Type your message... (Press Enter to send, Shift+Enter for new line)"}
            disabled={disabled}
            className={`message-textarea ${validationError ? 'error' : ''}`}
            rows={3}
            maxLength={MAX_MESSAGE_LENGTH + 100} // Allow typing beyond limit to show validation
          />
          
          <button
            type="submit"
            disabled={isDisabled}
            className={`send-button ${isLoading ? 'loading' : ''}`}
          >
            {isLoading ? 'Sending...' : 'Send'}
          </button>
        </div>
        
        <div className="input-footer">
          {validationError && (
            <div className="validation-error">
              {validationError}
            </div>
          )}
          
          <div className="character-count">
            {message.length}/{MAX_MESSAGE_LENGTH}
          </div>
        </div>
      </form>
    </div>
  )
}

export default MessageInput