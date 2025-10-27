// Error display component for comprehensive error handling
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import React from 'react'

const ErrorDisplay = ({ error, onRetry, onDismiss, type = 'error' }) => {
  if (!error) return null

  const getErrorIcon = () => {
    switch (type) {
      case 'warning':
        return '⚠️'
      case 'network':
        return '🌐'
      case 'timeout':
        return '⏱️'
      case 'server':
        return '🔧'
      default:
        return '❌'
    }
  }

  const getErrorTitle = () => {
    switch (type) {
      case 'network':
        return 'Connection Error'
      case 'timeout':
        return 'Request Timeout'
      case 'server':
        return 'Server Error'
      case 'validation':
        return 'Invalid Input'
      default:
        return 'Error'
    }
  }

  return (
    <div className={`error-display ${type}`}>
      <div className="error-content">
        <div className="error-header">
          <span className="error-icon">{getErrorIcon()}</span>
          <h4 className="error-title">{getErrorTitle()}</h4>
          {onDismiss && (
            <button 
              onClick={onDismiss}
              className="error-dismiss"
              aria-label="Dismiss error"
            >
              ×
            </button>
          )}
        </div>
        
        <div className="error-body">
          <p className="error-message">{error}</p>
          
          <div className="error-actions">
            {onRetry && (
              <button 
                onClick={onRetry}
                className="error-retry-btn"
              >
                Try Again
              </button>
            )}
            
            {type === 'network' && (
              <div className="error-suggestions">
                <p>Suggestions:</p>
                <ul>
                  <li>Check your internet connection</li>
                  <li>Verify the backend server is running</li>
                  <li>Try refreshing the page</li>
                </ul>
              </div>
            )}
            
            {type === 'timeout' && (
              <div className="error-suggestions">
                <p>The request took too long. This might be due to:</p>
                <ul>
                  <li>Slow internet connection</li>
                  <li>Server overload</li>
                  <li>Complex query processing</li>
                </ul>
              </div>
            )}
            
            {type === 'server' && (
              <div className="error-suggestions">
                <p>Server is experiencing issues:</p>
                <ul>
                  <li>Try again in a few moments</li>
                  <li>Contact support if the problem persists</li>
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ErrorDisplay