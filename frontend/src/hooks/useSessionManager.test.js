// useSessionManager hook tests
// Based on React Testing Library and Vitest best practices

import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import useSessionManager from './useSessionManager'
import * as api from '../services/api.js'

// Mock the API module
vi.mock('../services/api.js', () => ({
  createSession: vi.fn(),
  getSessions: vi.fn(),
  getSession: vi.fn(),
  updateSession: vi.fn(),
  deleteSession: vi.fn()
}))

describe('useSessionManager', () => {
  const mockSessions = [
    {
      id: 1,
      title: 'Session 1',
      message_count: 5,
      created_at: '2025-01-27T10:00:00Z',
      updated_at: '2025-01-27T11:00:00Z'
    },
    {
      id: 2,
      title: 'Session 2',
      message_count: 3,
      created_at: '2025-01-27T09:00:00Z',
      updated_at: '2025-01-27T10:30:00Z'
    }
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    // Default successful responses
    api.getSessions.mockResolvedValue(mockSessions)
    api.createSession.mockResolvedValue({
      id: 3,
      title: 'New Session',
      message_count: 0,
      created_at: '2025-01-27T12:00:00Z',
      updated_at: '2025-01-27T12:00:00Z'
    })
    api.getSession.mockResolvedValue(mockSessions[0])
    api.updateSession.mockResolvedValue({
      ...mockSessions[0],
      title: 'Updated Session'
    })
    api.deleteSession.mockResolvedValue()
  })

  it('initializes with empty state', async () => {
    const { result } = renderHook(() => useSessionManager())
    
    // Check initial state before any async operations
    expect(result.current.sessions).toEqual([])
    expect(result.current.activeSession).toBeNull()
    expect(result.current.initialized).toBe(false)
    expect(result.current.error).toBeNull()
    
    // Wait for initialization to complete
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
  })

  it('loads sessions on initialization', async () => {
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    expect(api.getSessions).toHaveBeenCalledTimes(1)
    expect(result.current.sessions).toEqual(mockSessions)
    expect(result.current.activeSession).toEqual(mockSessions[0])
  })

  it('handles loading sessions error', async () => {
    const error = new Error('Failed to load sessions')
    api.getSessions.mockRejectedValue(error)
    
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    expect(result.current.sessions).toEqual([])
    expect(result.current.error).toBe('Failed to load sessions')
  })

  it('creates new session successfully', async () => {
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    let newSession
    await act(async () => {
      newSession = await result.current.createNewSession({ title: 'Test Session' })
    })
    
    expect(api.createSession).toHaveBeenCalledWith({ title: 'Test Session' })
    expect(newSession).toEqual({
      id: 3,
      title: 'New Session',
      message_count: 0,
      created_at: '2025-01-27T12:00:00Z',
      updated_at: '2025-01-27T12:00:00Z'
    })
    expect(result.current.activeSession).toEqual(newSession)
    expect(result.current.sessions[0]).toEqual(newSession)
  })

  it('handles create session error', async () => {
    const error = new Error('Failed to create session')
    api.createSession.mockRejectedValue(error)
    
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    let newSession
    await act(async () => {
      newSession = await result.current.createNewSession()
    })
    
    expect(newSession).toBeNull()
    expect(result.current.error).toBe('Failed to create session')
  })

  it('switches to existing session', async () => {
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    let switchedSession
    await act(async () => {
      switchedSession = await result.current.switchSession(2)
    })
    
    expect(switchedSession).toEqual(mockSessions[1])
    expect(result.current.activeSession).toEqual(mockSessions[1])
    expect(api.getSession).not.toHaveBeenCalled() // Should use existing session
  })

  it('fetches session when switching to unknown session', async () => {
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    let switchedSession
    await act(async () => {
      switchedSession = await result.current.switchSession(99)
    })
    
    expect(api.getSession).toHaveBeenCalledWith(99)
    expect(switchedSession).toEqual(mockSessions[0])
    expect(result.current.activeSession).toEqual(mockSessions[0])
  })

  it('handles switch session error', async () => {
    const error = new Error('Session not found')
    api.getSession.mockRejectedValue(error)
    
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    let switchedSession
    await act(async () => {
      switchedSession = await result.current.switchSession(99)
    })
    
    expect(switchedSession).toBeNull()
    expect(result.current.error).toBe('Session not found')
  })

  it('updates session data successfully', async () => {
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    let updatedSession
    await act(async () => {
      updatedSession = await result.current.updateSessionData(1, { title: 'Updated Session' })
    })
    
    expect(api.updateSession).toHaveBeenCalledWith(1, { title: 'Updated Session' })
    expect(updatedSession.title).toBe('Updated Session')
    expect(result.current.sessions[0].title).toBe('Updated Session')
    expect(result.current.activeSession.title).toBe('Updated Session')
  })

  it('handles update session error', async () => {
    const error = new Error('Failed to update session')
    api.updateSession.mockRejectedValue(error)
    
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    let updatedSession
    await act(async () => {
      updatedSession = await result.current.updateSessionData(1, { title: 'Updated Session' })
    })
    
    expect(updatedSession).toBeNull()
    expect(result.current.error).toBe('Failed to update session')
  })

  it('deletes session successfully', async () => {
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    let deleteResult
    await act(async () => {
      deleteResult = await result.current.deleteSessionById(1)
    })
    
    expect(api.deleteSession).toHaveBeenCalledWith(1)
    expect(deleteResult).toBe(true)
    expect(result.current.sessions).toHaveLength(1)
    expect(result.current.sessions[0].id).toBe(2)
    expect(result.current.activeSession.id).toBe(2) // Should switch to remaining session
  })

  it('handles delete session error', async () => {
    const error = new Error('Failed to delete session')
    api.deleteSession.mockRejectedValue(error)
    
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    let deleteResult
    await act(async () => {
      deleteResult = await result.current.deleteSessionById(1)
    })
    
    expect(deleteResult).toBe(false)
    expect(result.current.error).toBe('Failed to delete session')
    expect(result.current.sessions).toHaveLength(2) // Should remain unchanged
  })

  it('clears active session when deleting last session', async () => {
    // Start with only one session
    api.getSessions.mockResolvedValue([mockSessions[0]])
    
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    await act(async () => {
      await result.current.deleteSessionById(1)
    })
    
    expect(result.current.sessions).toHaveLength(0)
    expect(result.current.activeSession).toBeNull()
  })

  it('refreshes active session data', async () => {
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    const refreshedSession = {
      ...mockSessions[0],
      message_count: 10
    }
    api.getSession.mockResolvedValue(refreshedSession)
    
    let result_session
    await act(async () => {
      result_session = await result.current.refreshActiveSession()
    })
    
    expect(api.getSession).toHaveBeenCalledWith(1)
    expect(result_session.message_count).toBe(10)
    expect(result.current.activeSession.message_count).toBe(10)
    expect(result.current.sessions[0].message_count).toBe(10)
  })

  it('validates required parameters', async () => {
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.initialized).toBe(true)
    })
    
    // Test switch session without ID
    let switchResult
    await act(async () => {
      switchResult = await result.current.switchSession(null)
    })
    
    expect(switchResult).toBeNull()
    await waitFor(() => {
      expect(result.current.error).toBe('Session ID is required')
    })
    
    // Clear error and test update without ID
    act(() => {
      result.current.clearError()
    })
    
    let updateResult
    await act(async () => {
      updateResult = await result.current.updateSessionData(null, { title: 'Test' })
    })
    
    expect(updateResult).toBeNull()
    await waitFor(() => {
      expect(result.current.error).toBe('Session ID is required')
    })
    
    // Clear error and test delete without ID
    act(() => {
      result.current.clearError()
    })
    
    let deleteResult
    await act(async () => {
      deleteResult = await result.current.deleteSessionById(null)
    })
    
    expect(deleteResult).toBe(false)
    await waitFor(() => {
      expect(result.current.error).toBe('Session ID is required')
    })
  })

  it('clears error state', async () => {
    const error = new Error('Test error')
    api.getSessions.mockRejectedValue(error)
    
    const { result } = renderHook(() => useSessionManager())
    
    await waitFor(() => {
      expect(result.current.error).toBe('Test error')
    })
    
    act(() => {
      result.current.clearError()
    })
    
    expect(result.current.error).toBeNull()
  })
})