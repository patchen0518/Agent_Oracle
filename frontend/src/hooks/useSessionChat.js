// Custom hook for session-based chat functionality
// Handles message sending, receiving, history loading, and synchronization

import { useState, useCallback, useEffect, useRef } from 'react'
import { sendSessionMessage, getSessionMessages } from '../services/api.js'
import useErrorHandler from './useErrorHandler.js'

const useSessionChat = (sessionId) => {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [initialized, setInitialized] = useState(false)
  
  const { error, handleError, clearError, retry, canRetry } = useErrorHandler()
  
  // Keep track of the current session ID to detect changes
  const currentSessionId = useRef(sessionId)
  const lastLoadedSessionId = useRef(null)

  // Load message history for the current session
  const loadMessages = useCallback(async (forceReload = false) => {
    if (!sessionId) {
      setMessages([])
      setInitialized(true)
      return []
    }

    // Skip loading if already loaded for this session and not forcing reload
    if (!forceReload && lastLoadedSessionId.current === sessionId) {
      return messages
    }

    setLoading(true)
    clearError()
    
    try {
      const messageHistory = await getSessionMessages(sessionId)
      setMessages(messageHistory)
      lastLoadedSessionId.current = sessionId
      return messageHistory
    } catch (err) {
      handleError(err)
      // On error, clear messages to avoid showing stale data
      setMessages([])
      return []
    } finally {
      setLoading(false)
    }
  }, [sessionId, messages, handleError, clearError])

  // Initialize messages when session changes
  useEffect(() => {
    if (currentSessionId.current !== sessionId) {
      currentSessionId.current = sessionId
      setInitialized(false)
      setMessages([])
      lastLoadedSessionId.current = null
    }

    if (!initialized && sessionId) {
      loadMessages().then(() => {
        setInitialized(true)
      })
    } else if (!sessionId) {
      setInitialized(true)
    }
  }, [sessionId, initialized, loadMessages])

  // Send a message in the current session
  const sendMessage = useCallback(async (messageContent) => {
    if (!sessionId) {
      handleError(new Error('No active session'))
      return null
    }

    if (!messageContent || typeof messageContent !== 'string' || messageContent.trim() === '') {
      handleError(new Error('Message content is required'))
      return null
    }

    setSending(true)
    clearError()
    
    try {
      // Add user message to local state immediately for better UX
      const userMessage = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: messageContent.trim(),
        timestamp: new Date().toISOString(),
        session_id: sessionId
      }
      
      setMessages(prev => [...prev, userMessage])
      
      // Send message to server and get AI response
      const aiResponse = await sendSessionMessage(sessionId, messageContent.trim())
      
      // Replace temporary user message and add AI response
      setMessages(prev => {
        // Remove temporary user message
        const withoutTemp = prev.filter(msg => msg.id !== userMessage.id)
        
        // Add both user message and AI response from server
        // The server should return the AI response, and we need to fetch updated history
        return [...withoutTemp]
      })
      
      // Reload messages to get the complete updated history from server
      await loadMessages(true)
      
      return aiResponse
    } catch (err) {
      // Remove temporary user message on error
      setMessages(prev => prev.filter(msg => msg.id !== `temp-${Date.now()}`))
      handleError(err)
      return null
    } finally {
      setSending(false)
    }
  }, [sessionId, handleError, clearError, loadMessages])

  // Refresh message history from server
  const refreshMessages = useCallback(async () => {
    return await loadMessages(true)
  }, [loadMessages])

  // Retry last failed operation
  const retryLastOperation = useCallback(async () => {
    if (sending) {
      // Can't retry while sending
      return false
    }
    
    return await retry(loadMessages)
  }, [retry, loadMessages, sending])

  // Clear messages (useful when switching sessions)
  const clearMessages = useCallback(() => {
    setMessages([])
    setInitialized(false)
    lastLoadedSessionId.current = null
    clearError()
  }, [clearError])

  // Get message count
  const messageCount = messages.length

  // Check if there are any messages
  const hasMessages = messageCount > 0

  // Get last message
  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null

  // Check if last message is from user (useful for UI states)
  const lastMessageFromUser = lastMessage?.role === 'user'

  return {
    // State
    messages,
    loading,
    sending,
    initialized,
    error,
    canRetry,
    messageCount,
    hasMessages,
    lastMessage,
    lastMessageFromUser,
    
    // Actions
    sendMessage,
    loadMessages,
    refreshMessages,
    retryLastOperation,
    clearMessages,
    clearError
  }
}

export default useSessionChat