// Custom hook for comprehensive error handling
// Based on React v19+ documentation (Context 7 lookup: 2025-01-27)

import { useState, useCallback } from 'react'

const useErrorHandler = () => {
  const [error, setError] = useState(null)
  const [errorType, setErrorType] = useState('error')
  const [retryCount, setRetryCount] = useState(0)

  // Maximum retry attempts
  const MAX_RETRIES = 3

  // Parse error and determine type
  const parseError = useCallback((err) => {
    let message = 'An unexpected error occurred'
    let type = 'error'

    if (err?.response) {
      // HTTP error response
      const status = err.response.status
      const data = err.response.data

      if (status >= 400 && status < 500) {
        // Client errors
        type = 'validation'
        message = data?.detail || `Client error: ${status}`
      } else if (status >= 500) {
        // Server errors
        type = 'server'
        message = data?.detail || 'Server error occurred'
      }
    } else if (err?.request) {
      // Network error
      type = 'network'
      message = 'Unable to connect to server'
    } else if (err?.code === 'ECONNABORTED') {
      // Timeout error
      type = 'timeout'
      message = 'Request timed out'
    } else if (err?.message) {
      // Custom error message
      message = err.message
      
      // Determine type based on message content
      if (message.toLowerCase().includes('network')) {
        type = 'network'
      } else if (message.toLowerCase().includes('timeout')) {
        type = 'timeout'
      } else if (message.toLowerCase().includes('server')) {
        type = 'server'
      }
    }

    return { message, type }
  }, [])

  // Handle error with automatic parsing
  const handleError = useCallback((err) => {
    const { message, type } = parseError(err)
    setError(message)
    setErrorType(type)
    
    // Log error for debugging
    console.error('Error handled:', { error: err, message, type })
  }, [parseError])

  // Clear error state
  const clearError = useCallback(() => {
    setError(null)
    setErrorType('error')
    setRetryCount(0)
  }, [])

  // Retry with exponential backoff
  const retry = useCallback(async (retryFunction) => {
    if (retryCount >= MAX_RETRIES) {
      handleError(new Error('Maximum retry attempts reached'))
      return false
    }

    try {
      // Clear current error
      setError(null)
      
      // Calculate delay (exponential backoff)
      const delay = Math.pow(2, retryCount) * 1000 // 1s, 2s, 4s
      
      if (delay > 0) {
        await new Promise(resolve => setTimeout(resolve, delay))
      }

      // Attempt retry
      await retryFunction()
      
      // Success - reset retry count
      setRetryCount(0)
      return true
    } catch (err) {
      setRetryCount(prev => prev + 1)
      handleError(err)
      return false
    }
  }, [retryCount, handleError])

  // Check if retry is available
  const canRetry = retryCount < MAX_RETRIES

  return {
    error,
    errorType,
    retryCount,
    canRetry,
    handleError,
    clearError,
    retry
  }
}

export default useErrorHandler