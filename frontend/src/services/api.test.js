// API service tests
// Tests for session-based API functions with proper error handling

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock axios before importing the API service
vi.mock('axios', () => {
  const mockAxiosInstance = {
    post: vi.fn(),
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: {
        use: vi.fn()
      },
      response: {
        use: vi.fn()
      }
    }
  }
  
  return {
    default: {
      create: vi.fn(() => mockAxiosInstance)
    }
  }
})

// Import after mocking
import axios from 'axios'
import {
  createSession,
  getSessions,
  getSession,
  updateSession,
  deleteSession,
  sendSessionMessage,
  getSessionMessages,
  checkHealth
} from './api.js'

describe('API Service', () => {
  let mockAxiosInstance

  beforeEach(() => {
    vi.clearAllMocks()
    
    // Get the mocked axios instance
    mockAxiosInstance = axios.create()
    
    // Mock successful responses by default
    mockAxiosInstance.post.mockResolvedValue({ data: {} })
    mockAxiosInstance.get.mockResolvedValue({ data: {} })
    mockAxiosInstance.put.mockResolvedValue({ data: {} })
    mockAxiosInstance.delete.mockResolvedValue({ data: {} })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Session Management', () => {
    describe('createSession', () => {
      it('creates session with provided data', async () => {
        const sessionData = { title: 'Test Session' }
        const expectedResponse = { id: 1, title: 'Test Session', message_count: 0 }
        
        mockAxiosInstance.post.mockResolvedValue({ data: expectedResponse })
        
        const result = await createSession(sessionData)
        
        expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/v1/sessions/', sessionData)
        expect(result).toEqual(expectedResponse)
      })

      it('creates session with empty data', async () => {
        const expectedResponse = { id: 1, title: 'New Session', message_count: 0 }
        
        mockAxiosInstance.post.mockResolvedValue({ data: expectedResponse })
        
        const result = await createSession()
        
        expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/v1/sessions/', {})
        expect(result).toEqual(expectedResponse)
      })

      it('handles 400 error with custom message', async () => {
        const error = {
          response: {
            status: 400,
            data: { detail: 'Invalid session data' }
          }
        }
        
        mockAxiosInstance.post.mockRejectedValue(error)
        
        await expect(createSession()).rejects.toThrow('Invalid session data')
      })

      it('handles 500 error', async () => {
        const error = {
          response: {
            status: 500,
            data: {}
          }
        }
        
        mockAxiosInstance.post.mockRejectedValue(error)
        
        await expect(createSession()).rejects.toThrow('Server error - failed to create session')
      })

      it('handles network error', async () => {
        const error = { request: {} }
        
        mockAxiosInstance.post.mockRejectedValue(error)
        
        await expect(createSession()).rejects.toThrow('Unable to connect to server - check your internet connection')
      })
    })

    describe('getSessions', () => {
      it('retrieves all sessions', async () => {
        const expectedSessions = [
          { id: 1, title: 'Session 1', message_count: 5 },
          { id: 2, title: 'Session 2', message_count: 3 }
        ]
        
        mockAxiosInstance.get.mockResolvedValue({ data: expectedSessions })
        
        const result = await getSessions()
        
        expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/v1/sessions/')
        expect(result).toEqual(expectedSessions)
      })

      it('handles error response', async () => {
        const error = {
          response: {
            status: 500,
            data: { detail: 'Database error' }
          }
        }
        
        mockAxiosInstance.get.mockRejectedValue(error)
        
        await expect(getSessions()).rejects.toThrow('Database error')
      })

      it('handles network error', async () => {
        const error = { request: {} }
        
        mockAxiosInstance.get.mockRejectedValue(error)
        
        await expect(getSessions()).rejects.toThrow('Unable to connect to server')
      })
    })

    describe('getSession', () => {
      it('retrieves specific session', async () => {
        const sessionId = 1
        const expectedSession = { id: 1, title: 'Test Session', message_count: 5 }
        
        mockAxiosInstance.get.mockResolvedValue({ data: expectedSession })
        
        const result = await getSession(sessionId)
        
        expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/v1/sessions/1')
        expect(result).toEqual(expectedSession)
      })

      it('handles 404 error', async () => {
        const error = {
          response: {
            status: 404,
            data: {}
          }
        }
        
        mockAxiosInstance.get.mockRejectedValue(error)
        
        await expect(getSession(1)).rejects.toThrow('Session not found')
      })

      it('handles other error responses', async () => {
        const error = {
          response: {
            status: 500,
            data: { detail: 'Server error' }
          }
        }
        
        mockAxiosInstance.get.mockRejectedValue(error)
        
        await expect(getSession(1)).rejects.toThrow('Server error')
      })
    })

    describe('updateSession', () => {
      it('updates session with provided data', async () => {
        const sessionId = 1
        const updates = { title: 'Updated Session' }
        const expectedResponse = { id: 1, title: 'Updated Session', message_count: 5 }
        
        mockAxiosInstance.put.mockResolvedValue({ data: expectedResponse })
        
        const result = await updateSession(sessionId, updates)
        
        expect(mockAxiosInstance.put).toHaveBeenCalledWith('/api/v1/sessions/1', updates)
        expect(result).toEqual(expectedResponse)
      })

      it('handles 404 error', async () => {
        const error = {
          response: {
            status: 404,
            data: {}
          }
        }
        
        mockAxiosInstance.put.mockRejectedValue(error)
        
        await expect(updateSession(1, {})).rejects.toThrow('Session not found')
      })

      it('handles 400 error', async () => {
        const error = {
          response: {
            status: 400,
            data: { detail: 'Invalid data' }
          }
        }
        
        mockAxiosInstance.put.mockRejectedValue(error)
        
        await expect(updateSession(1, {})).rejects.toThrow('Invalid data')
      })
    })

    describe('deleteSession', () => {
      it('deletes session successfully', async () => {
        const sessionId = 1
        const expectedResponse = { success: true }
        
        mockAxiosInstance.delete.mockResolvedValue({ data: expectedResponse })
        
        const result = await deleteSession(sessionId)
        
        expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/api/v1/sessions/1')
        expect(result).toEqual(expectedResponse)
      })

      it('handles 404 error', async () => {
        const error = {
          response: {
            status: 404,
            data: {}
          }
        }
        
        mockAxiosInstance.delete.mockRejectedValue(error)
        
        await expect(deleteSession(1)).rejects.toThrow('Session not found')
      })

      it('handles other errors', async () => {
        const error = {
          response: {
            status: 500,
            data: { detail: 'Delete failed' }
          }
        }
        
        mockAxiosInstance.delete.mockRejectedValue(error)
        
        await expect(deleteSession(1)).rejects.toThrow('Delete failed')
      })
    })
  })

  describe('Session Chat', () => {
    describe('sendSessionMessage', () => {
      it('sends message to session', async () => {
        const sessionId = 1
        const message = 'Hello, world!'
        const expectedResponse = {
          id: 1,
          session_id: 1,
          role: 'assistant',
          content: 'Hi there!',
          timestamp: '2025-01-27T10:00:00Z'
        }
        
        mockAxiosInstance.post.mockResolvedValue({ data: expectedResponse })
        
        const result = await sendSessionMessage(sessionId, message)
        
        expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/v1/sessions/1/chat', {
          message: message
        })
        expect(result).toEqual(expectedResponse)
      })

      it('handles 404 error for invalid session', async () => {
        const error = {
          response: {
            status: 404,
            data: {}
          }
        }
        
        mockAxiosInstance.post.mockRejectedValue(error)
        
        await expect(sendSessionMessage(1, 'Hello')).rejects.toThrow('Session not found')
      })

      it('handles 400 error for invalid message', async () => {
        const error = {
          response: {
            status: 400,
            data: { detail: 'Invalid message format' }
          }
        }
        
        mockAxiosInstance.post.mockRejectedValue(error)
        
        await expect(sendSessionMessage(1, 'Hello')).rejects.toThrow('Invalid message format')
      })

      it('handles 401 authentication error', async () => {
        const error = {
          response: {
            status: 401,
            data: {}
          }
        }
        
        mockAxiosInstance.post.mockRejectedValue(error)
        
        await expect(sendSessionMessage(1, 'Hello')).rejects.toThrow('Authentication failed - API key invalid')
      })

      it('handles 429 rate limit error', async () => {
        const error = {
          response: {
            status: 429,
            data: {}
          }
        }
        
        mockAxiosInstance.post.mockRejectedValue(error)
        
        await expect(sendSessionMessage(1, 'Hello')).rejects.toThrow('Rate limit exceeded - please wait before sending another message')
      })

      it('handles 502 service unavailable error', async () => {
        const error = {
          response: {
            status: 502,
            data: {}
          }
        }
        
        mockAxiosInstance.post.mockRejectedValue(error)
        
        await expect(sendSessionMessage(1, 'Hello')).rejects.toThrow('AI service temporarily unavailable')
      })

      it('handles timeout error', async () => {
        const error = { code: 'ECONNABORTED' }
        
        mockAxiosInstance.post.mockRejectedValue(error)
        
        await expect(sendSessionMessage(1, 'Hello')).rejects.toThrow('Request timed out - the server is taking too long to respond')
      })
    })

    describe('getSessionMessages', () => {
      it('retrieves messages for session', async () => {
        const sessionId = 1
        const expectedMessages = [
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
        
        mockAxiosInstance.get.mockResolvedValue({ data: expectedMessages })
        
        const result = await getSessionMessages(sessionId)
        
        expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/v1/sessions/1/messages')
        expect(result).toEqual(expectedMessages)
      })

      it('handles 404 error for invalid session', async () => {
        const error = {
          response: {
            status: 404,
            data: {}
          }
        }
        
        mockAxiosInstance.get.mockRejectedValue(error)
        
        await expect(getSessionMessages(1)).rejects.toThrow('Session not found')
      })

      it('handles other errors', async () => {
        const error = {
          response: {
            status: 500,
            data: { detail: 'Database error' }
          }
        }
        
        mockAxiosInstance.get.mockRejectedValue(error)
        
        await expect(getSessionMessages(1)).rejects.toThrow('Database error')
      })
    })
  })

  describe('Health Check', () => {
    describe('checkHealth', () => {
      it('returns health status', async () => {
        const expectedHealth = {
          status: 'healthy',
          timestamp: '2025-01-27T10:00:00Z',
          version: '1.0.0'
        }
        
        mockAxiosInstance.get.mockResolvedValue({ data: expectedHealth })
        
        const result = await checkHealth()
        
        expect(mockAxiosInstance.get).toHaveBeenCalledWith('/health')
        expect(result).toEqual(expectedHealth)
      })

      it('handles unhealthy backend response', async () => {
        const error = {
          response: {
            status: 503,
            data: {}
          }
        }
        
        mockAxiosInstance.get.mockRejectedValue(error)
        
        await expect(checkHealth()).rejects.toThrow('Backend unhealthy (HTTP 503)')
      })

      it('handles unreachable backend', async () => {
        const error = { request: {} }
        
        mockAxiosInstance.get.mockRejectedValue(error)
        
        await expect(checkHealth()).rejects.toThrow('Backend server is not reachable')
      })

      it('handles general health check failure', async () => {
        const error = { message: 'Unknown error' }
        
        mockAxiosInstance.get.mockRejectedValue(error)
        
        await expect(checkHealth()).rejects.toThrow('Health check failed')
      })
    })
  })

  describe('Error Handling', () => {
    it('preserves response error properties', async () => {
      const originalError = {
        response: {
          status: 400,
          data: { detail: 'Test error' }
        },
        config: { url: '/test' },
        isAxiosError: true
      }
      
      mockAxiosInstance.post.mockRejectedValue(originalError)
      
      try {
        await createSession()
      } catch (error) {
        expect(error.response).toEqual(originalError.response)
        expect(error.message).toBe('Test error')
      }
    })

    it('handles errors without response data', async () => {
      const error = {
        response: {
          status: 500,
          data: null
        }
      }
      
      mockAxiosInstance.get.mockRejectedValue(error)
      
      await expect(getSessions()).rejects.toThrow('Failed to load sessions')
    })

    it('handles errors with empty response data', async () => {
      const error = {
        response: {
          status: 400,
          data: {}
        }
      }
      
      mockAxiosInstance.post.mockRejectedValue(error)
      
      await expect(createSession()).rejects.toThrow('Invalid session data')
    })
  })
})