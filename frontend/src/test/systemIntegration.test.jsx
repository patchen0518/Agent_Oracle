/**
 * Complete system integration tests for session management workflows.
 * 
 * Tests the complete user journey from session creation to chat interactions,
 * verifying frontend-backend integration and user experience flows.
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import App from '../App'

// Mock the API functions
vi.mock('../services/api', () => ({
  checkHealth: vi.fn(),
  getSessions: vi.fn(),
  createSession: vi.fn(),
  getSession: vi.fn(),
  updateSession: vi.fn(),
  deleteSession: vi.fn(),
  sendSessionMessage: vi.fn(),
  getSessionMessages: vi.fn()
}))

import {
  checkHealth,
  getSessions,
  createSession,
  getSession,
  updateSession,
  deleteSession,
  sendSessionMessage,
  getSessionMessages
} from '../services/api'

describe('Complete System Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    
    // Default successful health check
    checkHealth.mockResolvedValue({ status: 'healthy' })
    
    // Default empty sessions
    getSessions.mockResolvedValue([])
    getSessionMessages.mockResolvedValue([])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Complete User Journey: Session Creation to Chat', () => {
    it('handles complete workflow from session creation to multiple chat exchanges', async () => {
      const user = userEvent.setup()
      
      // Mock API responses for complete workflow
      const mockSession = {
        id: 1,
        title: 'New Session',
        message_count: 0,
        created_at: '2025-01-27T10:00:00Z',
        updated_at: '2025-01-27T10:00:00Z',
        model_used: 'gemini-2.0-flash-exp',
        session_metadata: {}
      }
      
      const mockMessages = [
        {
          id: 1,
          session_id: 1,
          role: 'user',
          content: 'Hello, what can you help me with?',
          timestamp: '2025-01-27T10:01:00Z',
          message_metadata: {}
        },
        {
          id: 2,
          session_id: 1,
          role: 'assistant',
          content: 'Hello! I\'m Oracle, your AI assistant. I can help with a wide variety of topics including programming, science, and general questions. What would you like to know?',
          timestamp: '2025-01-27T10:01:30Z',
          message_metadata: {}
        },
        {
          id: 3,
          session_id: 1,
          role: 'user',
          content: 'Tell me about Python programming',
          timestamp: '2025-01-27T10:02:00Z',
          message_metadata: {}
        },
        {
          id: 4,
          session_id: 1,
          role: 'assistant',
          content: 'Python is a high-level, interpreted programming language known for its simplicity and readability. It\'s great for beginners and widely used in web development, data science, AI, and automation.',
          timestamp: '2025-01-27T10:02:30Z',
          message_metadata: {}
        }
      ]
      
      // Setup progressive API responses
      getSessions
        .mockResolvedValueOnce([]) // Initially empty
        .mockResolvedValueOnce([mockSession]) // After session creation
        .mockResolvedValue([{ ...mockSession, message_count: 4 }]) // After messages
      
      createSession.mockResolvedValue(mockSession)
      getSession.mockResolvedValue({ ...mockSession, message_count: 4 })
      getSessionMessages
        .mockResolvedValueOnce([]) // Initially empty
        .mockResolvedValueOnce(mockMessages.slice(0, 2)) // After first message
        .mockResolvedValue(mockMessages) // After second message
      
      sendSessionMessage
        .mockResolvedValueOnce({
          user_message: mockMessages[0],
          assistant_message: mockMessages[1],
          session: { ...mockSession, message_count: 2 }
        })
        .mockResolvedValueOnce({
          user_message: mockMessages[2],
          assistant_message: mockMessages[3],
          session: { ...mockSession, message_count: 4 }
        })
      
      render(<App />)
      
      // Step 1: Verify initial empty state
      await waitFor(() => {
        expect(screen.getByText('Create or select a session to start chatting.')).toBeInTheDocument()
      })
      
      // Step 2: Create new session
      const createButton = screen.getByRole('button', { name: /create new session/i })
      await user.click(createButton)
      
      // Verify session creation API call
      await waitFor(() => {
        expect(createSession).toHaveBeenCalledWith({ title: 'New Session' })
      })
      
      // Step 3: Verify session appears in sidebar
      await waitFor(() => {
        expect(screen.getByText('New Session')).toBeInTheDocument()
      })
      
      // Step 4: Send first message
      const messageInput = screen.getByPlaceholderText(/type your message/i)
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      await user.type(messageInput, 'Hello, what can you help me with?')
      await user.click(sendButton)
      
      // Verify first message API call
      await waitFor(() => {
        expect(sendSessionMessage).toHaveBeenCalledWith(1, 'Hello, what can you help me with?')
      })
      
      // Step 5: Verify first message appears
      await waitFor(() => {
        expect(screen.getByText('Hello, what can you help me with?')).toBeInTheDocument()
        expect(screen.getByText(/Hello! I'm Oracle, your AI assistant/)).toBeInTheDocument()
      })
      
      // Step 6: Send second message
      await user.clear(messageInput)
      await user.type(messageInput, 'Tell me about Python programming')
      await user.click(sendButton)
      
      // Verify second message API call
      await waitFor(() => {
        expect(sendSessionMessage).toHaveBeenCalledWith(1, 'Tell me about Python programming')
      })
      
      // Step 7: Verify second message appears
      await waitFor(() => {
        expect(screen.getByText('Tell me about Python programming')).toBeInTheDocument()
        expect(screen.getByText(/Python is a high-level, interpreted programming language/)).toBeInTheDocument()
      })
      
      // Step 8: Verify session message count updated
      await waitFor(() => {
        expect(screen.getByText('4 messages')).toBeInTheDocument()
      })
      
      // Verify all API calls were made correctly
      expect(getSessions).toHaveBeenCalledTimes(3)
      expect(createSession).toHaveBeenCalledTimes(1)
      expect(sendSessionMessage).toHaveBeenCalledTimes(2)
      expect(getSessionMessages).toHaveBeenCalledTimes(3)
    })

    it('handles session switching and maintains conversation context', async () => {
      const user = userEvent.setup()
      
      // Mock two sessions with different conversations
      const session1 = {
        id: 1,
        title: 'Python Discussion',
        message_count: 2,
        created_at: '2025-01-27T10:00:00Z',
        updated_at: '2025-01-27T10:01:00Z',
        model_used: 'gemini-2.0-flash-exp',
        session_metadata: {}
      }
      
      const session2 = {
        id: 2,
        title: 'JavaScript Help',
        message_count: 2,
        created_at: '2025-01-27T10:05:00Z',
        updated_at: '2025-01-27T10:06:00Z',
        model_used: 'gemini-2.0-flash-exp',
        session_metadata: {}
      }
      
      const session1Messages = [
        {
          id: 1,
          session_id: 1,
          role: 'user',
          content: 'What is Python?',
          timestamp: '2025-01-27T10:00:30Z',
          message_metadata: {}
        },
        {
          id: 2,
          session_id: 1,
          role: 'assistant',
          content: 'Python is a programming language.',
          timestamp: '2025-01-27T10:01:00Z',
          message_metadata: {}
        }
      ]
      
      const session2Messages = [
        {
          id: 3,
          session_id: 2,
          role: 'user',
          content: 'How do I use JavaScript?',
          timestamp: '2025-01-27T10:05:30Z',
          message_metadata: {}
        },
        {
          id: 4,
          session_id: 2,
          role: 'assistant',
          content: 'JavaScript is used for web development.',
          timestamp: '2025-01-27T10:06:00Z',
          message_metadata: {}
        }
      ]
      
      getSessions.mockResolvedValue([session1, session2])
      getSession
        .mockImplementation((sessionId) => {
          return sessionId === 1 ? Promise.resolve(session1) : Promise.resolve(session2)
        })
      getSessionMessages
        .mockImplementation((sessionId) => {
          return sessionId === 1 ? Promise.resolve(session1Messages) : Promise.resolve(session2Messages)
        })
      
      render(<App />)
      
      // Wait for sessions to load
      await waitFor(() => {
        expect(screen.getByText('Python Discussion')).toBeInTheDocument()
        expect(screen.getByText('JavaScript Help')).toBeInTheDocument()
      })
      
      // Click on first session
      await user.click(screen.getByText('Python Discussion'))
      
      // Verify first session content loads
      await waitFor(() => {
        expect(screen.getByText('What is Python?')).toBeInTheDocument()
        expect(screen.getByText('Python is a programming language.')).toBeInTheDocument()
      })
      
      // Switch to second session
      await user.click(screen.getByText('JavaScript Help'))
      
      // Verify second session content loads and first session content is gone
      await waitFor(() => {
        expect(screen.getByText('How do I use JavaScript?')).toBeInTheDocument()
        expect(screen.getByText('JavaScript is used for web development.')).toBeInTheDocument()
        expect(screen.queryByText('What is Python?')).not.toBeInTheDocument()
      })
      
      // Switch back to first session
      await user.click(screen.getByText('Python Discussion'))
      
      // Verify first session content is restored
      await waitFor(() => {
        expect(screen.getByText('What is Python?')).toBeInTheDocument()
        expect(screen.getByText('Python is a programming language.')).toBeInTheDocument()
        expect(screen.queryByText('How do I use JavaScript?')).not.toBeInTheDocument()
      })
    })
  })

  describe('Error Handling and Recovery', () => {
    it('handles session creation errors gracefully', async () => {
      const user = userEvent.setup()
      
      getSessions.mockResolvedValue([])
      createSession.mockRejectedValue(new Error('Failed to create session'))
      
      render(<App />)
      
      // Try to create session
      const createButton = screen.getByRole('button', { name: /create new session/i })
      await user.click(createButton)
      
      // Verify error is displayed
      await waitFor(() => {
        expect(screen.getByText(/failed to create session/i)).toBeInTheDocument()
      })
      
      // Verify user can retry
      createSession.mockResolvedValueOnce({
        id: 1,
        title: 'New Session',
        message_count: 0,
        created_at: '2025-01-27T10:00:00Z',
        updated_at: '2025-01-27T10:00:00Z',
        model_used: 'gemini-2.0-flash-exp',
        session_metadata: {}
      })
      getSessions.mockResolvedValue([{
        id: 1,
        title: 'New Session',
        message_count: 0,
        created_at: '2025-01-27T10:00:00Z',
        updated_at: '2025-01-27T10:00:00Z',
        model_used: 'gemini-2.0-flash-exp',
        session_metadata: {}
      }])
      
      // Click retry or create again
      await user.click(createButton)
      
      // Verify success
      await waitFor(() => {
        expect(screen.getByText('New Session')).toBeInTheDocument()
        expect(screen.queryByText(/failed to create session/i)).not.toBeInTheDocument()
      })
    })

    it('handles message sending errors with retry capability', async () => {
      const user = userEvent.setup()
      
      const mockSession = {
        id: 1,
        title: 'Error Test Session',
        message_count: 0,
        created_at: '2025-01-27T10:00:00Z',
        updated_at: '2025-01-27T10:00:00Z',
        model_used: 'gemini-2.0-flash-exp',
        session_metadata: {}
      }
      
      getSessions.mockResolvedValue([mockSession])
      getSession.mockResolvedValue(mockSession)
      getSessionMessages.mockResolvedValue([])
      
      // First attempt fails, second succeeds
      sendSessionMessage
        .mockRejectedValueOnce(new Error('Network error - please check your connection'))
        .mockResolvedValueOnce({
          user_message: {
            id: 1,
            session_id: 1,
            role: 'user',
            content: 'Test message',
            timestamp: '2025-01-27T10:01:00Z',
            message_metadata: {}
          },
          assistant_message: {
            id: 2,
            session_id: 1,
            role: 'assistant',
            content: 'Message sent successfully after retry',
            timestamp: '2025-01-27T10:01:30Z',
            message_metadata: {}
          },
          session: { ...mockSession, message_count: 2 }
        })
      
      render(<App />)
      
      // Wait for session to load and click it
      await waitFor(() => {
        expect(screen.getByText('Error Test Session')).toBeInTheDocument()
      })
      await user.click(screen.getByText('Error Test Session'))
      
      // Send message that will fail
      const messageInput = screen.getByPlaceholderText(/type your message/i)
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      await user.type(messageInput, 'Test message')
      await user.click(sendButton)
      
      // Verify error is displayed
      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument()
      })
      
      // Verify retry button appears and works
      const retryButton = screen.getByRole('button', { name: /try again/i })
      await user.click(retryButton)
      
      // Verify success after retry
      await waitFor(() => {
        expect(screen.getByText('Test message')).toBeInTheDocument()
        expect(screen.getByText('Message sent successfully after retry')).toBeInTheDocument()
        expect(screen.queryByText(/network error/i)).not.toBeInTheDocument()
      })
    })

    it('handles backend connectivity issues', async () => {
      const user = userEvent.setup()
      
      // Mock backend being down
      checkHealth.mockRejectedValue(new Error('Backend server is not reachable'))
      getSessions.mockRejectedValue(new Error('Unable to connect to server'))
      
      render(<App />)
      
      // Verify backend status shows as down
      await waitFor(() => {
        expect(screen.getByText(/backend.*down/i)).toBeInTheDocument()
      })
      
      // Verify appropriate error message is shown
      await waitFor(() => {
        expect(screen.getByText(/unable to connect to server/i)).toBeInTheDocument()
      })
      
      // Simulate backend coming back online
      checkHealth.mockResolvedValue({ status: 'healthy' })
      getSessions.mockResolvedValue([])
      
      // The app should recover automatically or allow manual retry
      // This would depend on the specific implementation of error recovery
    })
  })

  describe('Performance and User Experience', () => {
    it('handles large conversation histories efficiently', async () => {
      const user = userEvent.setup()
      
      // Create a session with many messages
      const mockSession = {
        id: 1,
        title: 'Large Conversation',
        message_count: 100,
        created_at: '2025-01-27T09:00:00Z',
        updated_at: '2025-01-27T10:00:00Z',
        model_used: 'gemini-2.0-flash-exp',
        session_metadata: {}
      }
      
      // Generate 100 messages
      const largeMessageHistory = []
      for (let i = 1; i <= 100; i++) {
        largeMessageHistory.push({
          id: i * 2 - 1,
          session_id: 1,
          role: 'user',
          content: `User message ${i}`,
          timestamp: `2025-01-27T09:${String(i).padStart(2, '0')}:00Z`,
          message_metadata: {}
        })
        largeMessageHistory.push({
          id: i * 2,
          session_id: 1,
          role: 'assistant',
          content: `Assistant response ${i}`,
          timestamp: `2025-01-27T09:${String(i).padStart(2, '0')}:30Z`,
          message_metadata: {}
        })
      }
      
      getSessions.mockResolvedValue([mockSession])
      getSession.mockResolvedValue(mockSession)
      getSessionMessages.mockResolvedValue(largeMessageHistory)
      
      const startTime = performance.now()
      render(<App />)
      
      // Click on session with large history
      await waitFor(() => {
        expect(screen.getByText('Large Conversation')).toBeInTheDocument()
      })
      await user.click(screen.getByText('Large Conversation'))
      
      // Verify messages load (check for first and last messages)
      await waitFor(() => {
        expect(screen.getByText('User message 1')).toBeInTheDocument()
        expect(screen.getByText('Assistant response 100')).toBeInTheDocument()
      })
      
      const endTime = performance.now()
      const loadTime = endTime - startTime
      
      // Verify reasonable load time (should be under 2 seconds for good UX)
      expect(loadTime).toBeLessThan(2000)
      
      // Verify message count is displayed correctly
      expect(screen.getByText('100 messages')).toBeInTheDocument()
    })

    it('provides responsive feedback during operations', async () => {
      const user = userEvent.setup()
      
      const mockSession = {
        id: 1,
        title: 'Feedback Test',
        message_count: 0,
        created_at: '2025-01-27T10:00:00Z',
        updated_at: '2025-01-27T10:00:00Z',
        model_used: 'gemini-2.0-flash-exp',
        session_metadata: {}
      }
      
      getSessions.mockResolvedValue([mockSession])
      getSession.mockResolvedValue(mockSession)
      getSessionMessages.mockResolvedValue([])
      
      // Mock slow message sending
      sendSessionMessage.mockImplementation(() => 
        new Promise(resolve => 
          setTimeout(() => resolve({
            user_message: {
              id: 1,
              session_id: 1,
              role: 'user',
              content: 'Slow message',
              timestamp: '2025-01-27T10:01:00Z',
              message_metadata: {}
            },
            assistant_message: {
              id: 2,
              session_id: 1,
              role: 'assistant',
              content: 'Slow response',
              timestamp: '2025-01-27T10:01:30Z',
              message_metadata: {}
            },
            session: { ...mockSession, message_count: 2 }
          }), 1000)
        )
      )
      
      render(<App />)
      
      // Select session
      await waitFor(() => {
        expect(screen.getByText('Feedback Test')).toBeInTheDocument()
      })
      await user.click(screen.getByText('Feedback Test'))
      
      // Send message
      const messageInput = screen.getByPlaceholderText(/type your message/i)
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      await user.type(messageInput, 'Slow message')
      await user.click(sendButton)
      
      // Verify loading state is shown
      expect(screen.getByText(/sending/i)).toBeInTheDocument()
      
      // Verify send button is disabled during sending
      expect(sendButton).toBeDisabled()
      
      // Wait for completion
      await waitFor(() => {
        expect(screen.getByText('Slow message')).toBeInTheDocument()
        expect(screen.getByText('Slow response')).toBeInTheDocument()
      }, { timeout: 2000 })
      
      // Verify loading state is cleared
      expect(screen.queryByText(/sending/i)).not.toBeInTheDocument()
      expect(sendButton).not.toBeDisabled()
    })
  })

  describe('Accessibility and Usability', () => {
    it('supports keyboard navigation throughout the interface', async () => {
      const user = userEvent.setup()
      
      const mockSession = {
        id: 1,
        title: 'Keyboard Test',
        message_count: 0,
        created_at: '2025-01-27T10:00:00Z',
        updated_at: '2025-01-27T10:00:00Z',
        model_used: 'gemini-2.0-flash-exp',
        session_metadata: {}
      }
      
      getSessions.mockResolvedValue([mockSession])
      getSession.mockResolvedValue(mockSession)
      getSessionMessages.mockResolvedValue([])
      sendSessionMessage.mockResolvedValue({
        user_message: {
          id: 1,
          session_id: 1,
          role: 'user',
          content: 'Keyboard test message',
          timestamp: '2025-01-27T10:01:00Z',
          message_metadata: {}
        },
        assistant_message: {
          id: 2,
          session_id: 1,
          role: 'assistant',
          content: 'Keyboard navigation works great!',
          timestamp: '2025-01-27T10:01:30Z',
          message_metadata: {}
        },
        session: { ...mockSession, message_count: 2 }
      })
      
      render(<App />)
      
      // Wait for session to load
      await waitFor(() => {
        expect(screen.getByText('Keyboard Test')).toBeInTheDocument()
      })
      
      // Navigate to session using keyboard
      const sessionButton = screen.getByRole('button', { name: /keyboard test/i })
      sessionButton.focus()
      await user.keyboard('{Enter}')
      
      // Navigate to message input using Tab
      await user.keyboard('{Tab}')
      const messageInput = screen.getByPlaceholderText(/type your message/i)
      expect(messageInput).toHaveFocus()
      
      // Type message and send with Enter
      await user.type(messageInput, 'Keyboard test message')
      await user.keyboard('{Enter}')
      
      // Verify message was sent
      await waitFor(() => {
        expect(sendSessionMessage).toHaveBeenCalledWith(1, 'Keyboard test message')
      })
      
      await waitFor(() => {
        expect(screen.getByText('Keyboard test message')).toBeInTheDocument()
        expect(screen.getByText('Keyboard navigation works great!')).toBeInTheDocument()
      })
    })

    it('provides proper ARIA labels and screen reader support', async () => {
      const mockSession = {
        id: 1,
        title: 'Accessibility Test',
        message_count: 2,
        created_at: '2025-01-27T10:00:00Z',
        updated_at: '2025-01-27T10:01:00Z',
        model_used: 'gemini-2.0-flash-exp',
        session_metadata: {}
      }
      
      const mockMessages = [
        {
          id: 1,
          session_id: 1,
          role: 'user',
          content: 'Test message',
          timestamp: '2025-01-27T10:00:30Z',
          message_metadata: {}
        },
        {
          id: 2,
          session_id: 1,
          role: 'assistant',
          content: 'Test response',
          timestamp: '2025-01-27T10:01:00Z',
          message_metadata: {}
        }
      ]
      
      getSessions.mockResolvedValue([mockSession])
      getSession.mockResolvedValue(mockSession)
      getSessionMessages.mockResolvedValue(mockMessages)
      
      render(<App />)
      
      // Verify ARIA labels are present
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /accessibility test.*2 messages/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /create new session/i })).toBeInTheDocument()
        expect(screen.getByRole('textbox', { name: /message input/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /send message/i })).toBeInTheDocument()
      })
      
      // Click session and verify message accessibility
      const user = userEvent.setup()
      await user.click(screen.getByRole('button', { name: /accessibility test/i }))
      
      await waitFor(() => {
        // Verify messages have proper roles and labels
        const messages = screen.getAllByRole('article')
        expect(messages).toHaveLength(2)
        
        // Verify message content is accessible
        expect(screen.getByText('Test message')).toBeInTheDocument()
        expect(screen.getByText('Test response')).toBeInTheDocument()
      })
    })
  })
})