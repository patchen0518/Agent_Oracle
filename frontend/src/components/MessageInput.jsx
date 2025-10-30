// Message input component for chat interface
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import React, { useState, useCallback, memo, useRef, useEffect } from 'react'

const MessageInput = memo(({ onSendMessage, isLoading, disabled, placeholder }) => {
  const [message, setMessage] = useState('')
  const [validationError, setValidationError] = useState('')
  const [isFocused, setIsFocused] = useState(false)
  const textareaRef = useRef(null)

  // Maximum message length
  const MAX_MESSAGE_LENGTH = 4000

  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }, [message])

  // Handle input change with validation
  const handleInputChange = useCallback((e) => {
    const value = e.target.value
    setMessage(value)
    
    // Clear validation error when user starts typing
    if (validationError) {
      setValidationError('')
    }

    // Check length validation with better feedback
    if (value.length > MAX_MESSAGE_LENGTH) {
      setValidationError(`Message too long (${value.length}/${MAX_MESSAGE_LENGTH} characters)`)
    } else if (value.length > MAX_MESSAGE_LENGTH * 0.9) {
      // Warning when approaching limit
      setValidationError(`Approaching character limit (${value.length}/${MAX_MESSAGE_LENGTH})`)
    }
  }, [validationError, MAX_MESSAGE_LENGTH])

  // Handle form submission
  const handleSubmit = useCallback((e) => {
    e.preventDefault()
    
    // Validate message
    const trimmedMessage = message.trim()
    
    if (!trimmedMessage) {
      setValidationError('Please enter a message')
      textareaRef.current?.focus()
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
  }, [message, onSendMessage, MAX_MESSAGE_LENGTH])

  // Handle Enter key press (with Shift+Enter for new lines)
  const handleKeyPress = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }, [handleSubmit])

  // Handle focus events
  const handleFocus = useCallback(() => setIsFocused(true), [])
  const handleBlur = useCallback(() => setIsFocused(false), [])

  const isDisabled = disabled || isLoading || message.length > MAX_MESSAGE_LENGTH
  const isWarning = message.length > MAX_MESSAGE_LENGTH * 0.9
  const isError = message.length > MAX_MESSAGE_LENGTH

  return (
    <div className={`message-input ${isFocused ? 'focused' : ''}`}>
      <form onSubmit={handleSubmit} className="message-form">
        <div className="input-container">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            onFocus={handleFocus}
            onBlur={handleBlur}
            placeholder={disabled ? (placeholder || "Backend not connected...") : (placeholder || "Type your message... (Press Enter to send, Shift+Enter for new line)")}
            disabled={disabled}
            className={`message-textarea ${validationError ? 'error' : ''} ${isWarning ? 'warning' : ''}`}
            rows={3}
            maxLength={MAX_MESSAGE_LENGTH + 100} // Allow typing beyond limit to show validation
            aria-describedby="char-count validation-error"
          />
          
          <button
            type="submit"
            disabled={isDisabled}
            className={`send-button ${isLoading ? 'loading' : ''} ${isError ? 'error' : ''}`}
            aria-label={isLoading ? 'Sending message...' : 'Send message'}
          >
            {isLoading ? (
              <>
                <span className="loading-spinner"></span>
                Sending...
              </>
            ) : (
              'Send'
            )}
          </button>
        </div>
        
        <div className="input-footer">
          {validationError && (
            <div id="validation-error" className={`validation-error ${isError ? 'error' : 'warning'}`} role="alert">
              {validationError}
            </div>
          )}
          
          <div id="char-count" className={`character-count ${isWarning ? 'warning' : ''} ${isError ? 'error' : ''}`}>
            {message.length}/{MAX_MESSAGE_LENGTH}
          </div>
        </div>
      </form>
    </div>
  )
})

export default MessageInput