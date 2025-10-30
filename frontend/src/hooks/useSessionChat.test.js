// useSessionChat hook tests
// Based on React Testing Library and Vitest best practices

import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import useSessionChat from './useSessionChat'
import * as api from '../services/api.js'

// Mock the API module
vi.mock('../services/api.js', () => ({
  sendSessionMessage: vi.fn(),
  getSessionMessages: vi.fn()
}))

describe('useSessionChat', () => {
  const mockMessages = [
    {
      id: 1,
      session_id: 1,
      role: 'user',
      content: 'Hello',
      timestamp: '2025-01-27T10:00:00Z'
    },
    {
      id: 2,
      session_id: 1,
      role: 'assistant',
      content: 'Hi there!',
      timestamp: '2025-01-27T10:01:00Z'
    }
  ]

  const mockAiResponse = {
    id: 3,
    session_id: 1,
    role: 'assistant',
    content: 'How can I help you?',
    timestamp: '2025-01-27T10:02:00Z'
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Default successful responses
    api.getSessionMessages.mockResolvedValue(mockMessages)
    api.sendSessionMessage.mockResolvedValue(mockAiResponse)
  })

  it('initializes with empty state when no session ID', () => {
    const { result } = renderHook(() => useSessionChat(null))
    
    expect(result.current.messages).toEqual([])
    expect(result.current.loading).toBe(false)
    expect(result.current.sending).toBe(false)
    expect(result.current.initialized).toBe(true)
    expect(result.current.error).toBeNull()
    expect(result.current.messageCount).toBe(0)
    expect(result.current.hasMessages).toBe(false)
    expect(result.current.lastMessage).toBeNull()
  })

  it('loads messages on initialization with session ID', async () => {
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    expect(api.getSessionMessages).toHaveBeenCalledWith(1)
    expect(result.current.messages).toEqual(mockMessages)
    expect(result.current.messageCount).toBe(2)
    expect(result.current.hasMessages).toBe(true)
    expect(result.current.lastMessage).toEqual(mockMessages[1])
    expect(result.current.lastMessageFromUser).toBe(false)
  })

  it('handles loading messages error', async () => {
    const error = new Error('Failed to load messages')
    api.getSessionMessages.mockRejectedValue(error)
    
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    expect(result.current.messages).toEqual([])
    expect(result.current.error).toBe('Failed to load messages')
  })

  it('reloads messages when session ID changes', async () => {
    const { result, rerender } = renderHook(
      ({ sessionId }) => useSessionChat(sessionId),
      { initialProps: { sessionId: 1 } }
    )
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    expect(api.getSessionMessages).toHaveBeenCalledWith(1)
    
    // Change session ID
    const newMessages = [{ id: 4, session_id: 2, role: 'user', content: 'New session', timestamp: '2025-01-27T11:00:00Z' }]
    api.getSessionMessages.mockResolvedValue(newMessages)
    
    rerender({ sessionId: 2 })
    
    await waitFor(() => {
      expect(result.current.messages).toEqual(newMessages)
    })
    
    expect(api.getSessionMessages).toHaveBeenCalledWith(2)
  })

  it('sends message successfully', async () => {
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    // Mock updated messages after sending
    const updatedMessages = [...mockMessages, mockAiResponse]
    api.getSessionMessages.mockResolvedValue(updatedMessages)
    
    let response
    await act(async () => {
      response = await result.current.sendMessage('How are you?')
    })
    
    expect(api.sendSessionMessage).toHaveBeenCalledWith(1, 'How are you?')
    expect(response).toEqual(mockAiResponse)
    expect(api.getSessionMessages).toHaveBeenCalledWith(1) // Should reload messages
    expect(result.current.messages).toEqual(updatedMessages)
  })

  it('handles send message error', async () => {
    const error = new Error('Failed to send message')
    api.sendSessionMessage.mockRejectedValue(error)
    
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    let response
    await act(async () => {
      response = await result.current.sendMessage('Hello')
    })
    
    expect(response).toBeNull()
    expect(result.current.error).toBe('Failed to send message')
  })

  it('validates message content', async () => {
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    // Test empty message
    let response
    await act(async () => {
      response = await result.current.sendMessage('')
    })
    
    expect(response).toBeNull()
    await waitFor(() => {
      expect(result.current.error).toBe('Message content is required')
    })
    
    // Clear error and test whitespace-only message
    act(() => {
      result.current.clearError()
    })
    
    await act(async () => {
      response = await result.current.sendMessage('   ')
    })
    
    expect(response).toBeNull()
    await waitFor(() => {
      expect(result.current.error).toBe('Message content is required')
    })
    
    // Clear error and test null message
    act(() => {
      result.current.clearError()
    })
    
    await act(async () => {
      response = await result.current.sendMessage(null)
    })
    
    expect(response).toBeNull()
    await waitFor(() => {
      expect(result.current.error).toBe('Message content is required')
    })
  })

  it('prevents sending message without active session', async () => {
    const { result } = renderHook(() => useSessionChat(null))
    
    let response
    await act(async () => {
      response = await result.current.sendMessage('Hello')
    })
    
    expect(response).toBeNull()
    await waitFor(() => {
      expect(result.current.error).toBe('No active session')
    })
    expect(api.sendSessionMessage).not.toHaveBeenCalled()
  })

  it('shows temporary user message while sending', async () => {
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    // Mock a slow API response
    let resolveApiCall
    const apiPromise = new Promise(resolve => {
      resolveApiCall = resolve
    })
    api.sendSessionMessage.mockReturnValue(apiPromise)
    
    // Start sending message
    act(() => {
      result.current.sendMessage('Hello')
    })
    
    // Should show temporary message and sending state
    await waitFor(() => {
      expect(result.current.sending).toBe(true)
    })
    
    // Resolve API call
    act(() => {
      resolveApiCall(mockAiResponse)
    })
    
    await waitFor(() => {
      expect(result.current.sending).toBe(false)
    })
  })

  it('refreshes messages successfully', async () => {
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    const newMessages = [...mockMessages, { id: 5, session_id: 1, role: 'user', content: 'New message', timestamp: '2025-01-27T10:03:00Z' }]
    api.getSessionMessages.mockResolvedValue(newMessages)
    
    let refreshedMessages
    await act(async () => {
      refreshedMessages = await result.current.refreshMessages()
    })
    
    expect(refreshedMessages).toEqual(newMessages)
    expect(result.current.messages).toEqual(newMessages)
  })

  it('clears messages and state', () => {
    const { result } = renderHook(() => useSessionChat(1))
    
    act(() => {
      result.current.clearMessages()
    })
    
    expect(result.current.messages).toEqual([])
    expect(result.current.initialized).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('provides correct message metadata', async () => {
    const messagesWithUserLast = [
      ...mockMessages,
      {
        id: 3,
        session_id: 1,
        role: 'user',
        content: 'Latest message',
        timestamp: '2025-01-27T10:02:00Z'
      }
    ]
    
    api.getSessionMessages.mockResolvedValue(messagesWithUserLast)
    
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    expect(result.current.messageCount).toBe(3)
    expect(result.current.hasMessages).toBe(true)
    expect(result.current.lastMessage.content).toBe('Latest message')
    expect(result.current.lastMessageFromUser).toBe(true)
  })

  it('skips loading if already loaded for same session', async () => {
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    expect(api.getSessionMessages).toHaveBeenCalledTimes(1)
    
    // Call loadMessages again
    await act(async () => {
      await result.current.loadMessages()
    })
    
    // Should not call API again
    expect(api.getSessionMessages).toHaveBeenCalledTimes(1)
  })

  it('forces reload when requested', async () => {
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    expect(api.getSessionMessages).toHaveBeenCalledTimes(1)
    
    // Force reload
    await act(async () => {
      await result.current.loadMessages(true)
    })
    
    // Should call API again
    expect(api.getSessionMessages).toHaveBeenCalledTimes(2)
  })

  it('trims message content before sending', async () => {
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    await act(async () => {
      await result.current.sendMessage('  Hello World  ')
    })
    
    expect(api.sendSessionMessage).toHaveBeenCalledWith(1, 'Hello World')
  })

  it('clears error state', async () => {
    const error = new Error('Test error')
    api.getSessionMessages.mockRejectedValue(error)
    
    const { result } = renderHook(() => useSessionChat(1))
    
    await waitFor(() => {
      expect(result.current.error).toBe('Test error')
    })
    
    act(() => {
      result.current.clearError()
    })
    
    expect(result.current.error).toBeNull()
  })
})