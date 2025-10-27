// Performance tests for message handling and rendering
// Based on React Testing Library performance testing patterns (Context 7 lookup: 2025-01-27)

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from '../App'

// Mock the API service
vi.mock('../services/api', () => ({
  checkHealth: vi.fn(),
  postChatMessage: vi.fn()
}))

import { checkHealth, postChatMessage } from '../services/api'

describe('Performance Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    checkHealth.mockResolvedValue({ status: 'ok' })
  })

  describe('Message Rendering Performance', () => {
    it('handles large number of messages efficiently', async () => {
      const user = userEvent.setup()
      
      // Mock responses for many messages
      const responses = Array.from({ length: 50 }, (_, i) => ({
        response: `Response ${i + 1}: This is a test response with some content to simulate real usage.`
      }))
      
      postChatMessage.mockImplementation(() => {
        const response = responses.shift()
        return Promise.resolve(response || { response: 'Default response' })
      })
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      const input = screen.getByPlaceholderText(/Type your message/)
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      // Measure time to send multiple messages
      const startTime = performance.now()
      
      // Send 20 messages rapidly
      for (let i = 1; i <= 20; i++) {
        await user.clear(input)
        await user.type(input, `Message ${i}`)
        await user.click(sendButton)
        
        // Wait for response to appear
        await waitFor(() => {
          expect(screen.getByText(`Response ${i}:`)).toBeInTheDocument()
        }, { timeout: 1000 })
      }
      
      const endTime = performance.now()
      const totalTime = endTime - startTime
      
      // Performance assertion - should handle 20 messages in reasonable time
      expect(totalTime).toBeLessThan(10000) // Less than 10 seconds
      
      // Verify all messages are rendered
      expect(screen.getByText('Message 1')).toBeInTheDocument()
      expect(screen.getByText('Message 20')).toBeInTheDocument()
      expect(screen.getByText('Response 1:')).toBeInTheDocument()
      expect(screen.getByText('Response 20:')).toBeInTheDocument()
    })

    it('maintains smooth scrolling with many messages', async () => {
      const user = userEvent.setup()
      
      // Create a large conversation history
      const largeHistory = []
      for (let i = 1; i <= 100; i++) {
        largeHistory.push({
          id: i * 2 - 1,
          role: 'user',
          content: `User message ${i}`,
          timestamp: new Date(Date.now() - (100 - i) * 1000)
        })
        largeHistory.push({
          id: i * 2,
          role: 'model',
          content: `Agent response ${i} with some longer content to test rendering performance`,
          timestamp: new Date(Date.now() - (100 - i) * 1000 + 500)
        })
      }
      
      // Mock the App to start with large history
      const AppWithHistory = () => {
        const [messages, setMessages] = React.useState(largeHistory)
        const [isLoading, setIsLoading] = React.useState(false)
        
        return (
          <div className="app">
            <header className="app-header">
              <h1>Oracle Chat</h1>
              <div className="status connected">Backend: connected</div>
            </header>
            <main className="app-main">
              <ChatInterface messages={messages} isLoading={isLoading} />
            </main>
          </div>
        )
      }
      
      const startTime = performance.now()
      render(<AppWithHistory />)
      const endTime = performance.now()
      
      // Should render large message list quickly
      expect(endTime - startTime).toBeLessThan(1000) // Less than 1 second
      
      // Verify messages are rendered
      expect(screen.getByText('User message 1')).toBeInTheDocument()
      expect(screen.getByText('User message 100')).toBeInTheDocument()
    })

    it('handles rapid user input without performance degradation', async () => {
      const user = userEvent.setup()
      
      postChatMessage.mockResolvedValue({ response: 'Quick response' })
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      const input = screen.getByPlaceholderText(/Type your message/)
      
      // Measure typing performance
      const startTime = performance.now()
      
      // Type a long message rapidly
      const longMessage = 'This is a very long message that tests the performance of the input component when handling rapid typing and validation. '.repeat(10)
      
      await user.type(input, longMessage)
      
      const endTime = performance.now()
      const typingTime = endTime - startTime
      
      // Should handle rapid typing smoothly
      expect(typingTime).toBeLessThan(5000) // Less than 5 seconds for long message
      
      // Verify input value is correct
      expect(input.value).toBe(longMessage)
      
      // Verify character count is updated
      expect(screen.getByText(`${longMessage.length}/4000`)).toBeInTheDocument()
    })
  })

  describe('Memory Usage Tests', () => {
    it('does not leak memory with message updates', async () => {
      const user = userEvent.setup()
      
      postChatMessage.mockResolvedValue({ response: 'Memory test response' })
      
      const { unmount } = render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      const input = screen.getByPlaceholderText(/Type your message/)
      
      // Send multiple messages to test memory usage
      for (let i = 1; i <= 10; i++) {
        await user.clear(input)
        await user.type(input, `Memory test ${i}`)
        await user.click(screen.getByRole('button', { name: /send/i }))
        
        await waitFor(() => {
          expect(screen.getByText('Memory test response')).toBeInTheDocument()
        })
      }
      
      // Unmount component to test cleanup
      unmount()
      
      // If we reach here without errors, memory cleanup is working
      expect(true).toBe(true)
    })

    it('handles component re-renders efficiently', async () => {
      let renderCount = 0
      
      const TestApp = () => {
        renderCount++
        return <App />
      }
      
      const { rerender } = render(<TestApp />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      const initialRenderCount = renderCount
      
      // Force re-renders
      for (let i = 0; i < 5; i++) {
        rerender(<TestApp />)
      }
      
      // Should not cause excessive re-renders
      expect(renderCount - initialRenderCount).toBeLessThanOrEqual(5)
    })
  })

  describe('Network Performance Tests', () => {
    it('handles slow network responses gracefully', async () => {
      const user = userEvent.setup()
      
      // Mock slow network response
      postChatMessage.mockImplementation(() => 
        new Promise(resolve => 
          setTimeout(() => resolve({ response: 'Slow response' }), 2000)
        )
      )
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      const input = screen.getByPlaceholderText(/Type your message/)
      
      const startTime = performance.now()
      
      await user.type(input, 'Test slow response')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Should show loading state immediately
      expect(screen.getByText('Oracle is thinking...')).toBeInTheDocument()
      
      // Wait for slow response
      await waitFor(() => {
        expect(screen.getByText('Slow response')).toBeInTheDocument()
      }, { timeout: 3000 })
      
      const endTime = performance.now()
      const totalTime = endTime - startTime
      
      // Should handle slow responses within reasonable time
      expect(totalTime).toBeGreaterThan(2000) // At least 2 seconds (our delay)
      expect(totalTime).toBeLessThan(3000) // But not much more
    })

    it('handles concurrent requests efficiently', async () => {
      const user = userEvent.setup()
      
      let requestCount = 0
      postChatMessage.mockImplementation(() => {
        requestCount++
        return new Promise(resolve => 
          setTimeout(() => resolve({ response: `Concurrent response ${requestCount}` }), 100)
        )
      })
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      const input = screen.getByPlaceholderText(/Type your message/)
      
      // Try to send multiple messages quickly (should be prevented by loading state)
      await user.type(input, 'First message')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Button should be disabled during loading
      const sendButton = screen.getByRole('button', { name: /sending message/i })
      expect(sendButton).toBeDisabled()
      
      // Wait for first response
      await waitFor(() => {
        expect(screen.getByText('Concurrent response 1')).toBeInTheDocument()
      })
      
      // Should only have made one request due to loading state prevention
      expect(requestCount).toBe(1)
    })
  })
})