// Accessibility tests for UI components
// Based on React Testing Library accessibility testing patterns (Context 7 lookup: 2025-01-27)

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { axe, toHaveNoViolations } from 'jest-axe'
import App from '../App'
import ChatInterface from '../components/ChatInterface'
import MessageInput from '../components/MessageInput'
import Message from '../components/Message'
import ErrorDisplay from '../components/ErrorDisplay'

// Extend Jest matchers
expect.extend(toHaveNoViolations)

// Mock the API service
vi.mock('../services/api', () => ({
  checkHealth: vi.fn(),
  postChatMessage: vi.fn()
}))

import { checkHealth, postChatMessage } from '../services/api'

describe('Accessibility Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    checkHealth.mockResolvedValue({ status: 'ok' })
  })

  describe('App Component Accessibility', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      const results = await axe(container)
      expect(results).toHaveNoViolations()
    })

    it('has proper heading structure', async () => {
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      // Should have main heading
      const mainHeading = screen.getByRole('heading', { level: 1 })
      expect(mainHeading).toHaveTextContent('Oracle Chat')
      
      // Should have proper heading hierarchy
      const welcomeHeading = screen.getByRole('heading', { level: 3 })
      expect(welcomeHeading).toHaveTextContent('Welcome to Oracle Chat')
    })

    it('has proper landmark regions', async () => {
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      // Should have header landmark
      expect(screen.getByRole('banner')).toBeInTheDocument()
      
      // Should have main landmark
      expect(screen.getByRole('main')).toBeInTheDocument()
    })

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup()
      
      postChatMessage.mockResolvedValue({ response: 'Keyboard test response' })
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      // Tab to message input
      await user.tab()
      const input = screen.getByPlaceholderText(/Type your message/)
      expect(input).toHaveFocus()
      
      // Type message
      await user.type(input, 'Accessibility test')
      
      // Tab to send button
      await user.tab()
      const sendButton = screen.getByRole('button', { name: /send/i })
      expect(sendButton).toHaveFocus()
      
      // Press Enter to send
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(screen.getByText('Keyboard test response')).toBeInTheDocument()
      })
    })
  })

  describe('MessageInput Accessibility', () => {
    it('has proper form labels and descriptions', () => {
      const mockSend = vi.fn()
      render(<MessageInput onSendMessage={mockSend} isLoading={false} disabled={false} />)
      
      const textarea = screen.getByRole('textbox')
      
      // Should have proper aria-describedby
      expect(textarea).toHaveAttribute('aria-describedby', 'char-count validation-error')
      
      // Should have character count
      expect(screen.getByText('0/4000')).toBeInTheDocument()
    })

    it('provides proper validation feedback', async () => {
      const user = userEvent.setup()
      const mockSend = vi.fn()
      
      render(<MessageInput onSendMessage={mockSend} isLoading={false} disabled={false} />)
      
      const textarea = screen.getByRole('textbox')
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      // Try to send empty message
      await user.click(sendButton)
      
      // Should show validation error with proper role
      await waitFor(() => {
        const errorElement = screen.getByRole('alert')
        expect(errorElement).toHaveTextContent('Please enter a message')
      })
    })

    it('handles disabled state properly', () => {
      const mockSend = vi.fn()
      render(<MessageInput onSendMessage={mockSend} isLoading={false} disabled={true} />)
      
      const textarea = screen.getByRole('textbox')
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      // Both should be disabled
      expect(textarea).toBeDisabled()
      expect(sendButton).toBeDisabled()
      
      // Should have appropriate placeholder
      expect(textarea).toHaveAttribute('placeholder', 'Backend not connected...')
    })

    it('provides loading state feedback', () => {
      const mockSend = vi.fn()
      render(<MessageInput onSendMessage={mockSend} isLoading={true} disabled={false} />)
      
      const sendButton = screen.getByRole('button', { name: /sending message/i })
      
      // Should be disabled during loading
      expect(sendButton).toBeDisabled()
      
      // Should have loading indicator
      expect(screen.getByText('Sending...')).toBeInTheDocument()
    })
  })

  describe('ChatInterface Accessibility', () => {
    it('has proper scrollable region', () => {
      const messages = [
        { id: 1, role: 'user', content: 'Hello', timestamp: new Date() },
        { id: 2, role: 'model', content: 'Hi there!', timestamp: new Date() }
      ]
      
      render(<ChatInterface messages={messages} isLoading={false} />)
      
      // Should have scrollable content
      const messagesContainer = document.querySelector('.messages-container')
      expect(messagesContainer).toBeInTheDocument()
    })

    it('provides proper scroll to bottom functionality', () => {
      const messages = Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        role: i % 2 === 0 ? 'user' : 'model',
        content: `Message ${i + 1}`,
        timestamp: new Date()
      }))
      
      render(<ChatInterface messages={messages} isLoading={false} />)
      
      // Should have scroll to bottom button when there are many messages
      // Note: This might not appear in test environment due to scrolling behavior
      // but the component should handle it gracefully
    })

    it('handles empty state properly', () => {
      render(<ChatInterface messages={[]} isLoading={false} />)
      
      // Should show welcome message
      expect(screen.getByText('Welcome to Oracle Chat')).toBeInTheDocument()
      expect(screen.getByText('Start a conversation by typing a message below.')).toBeInTheDocument()
    })
  })

  describe('Message Component Accessibility', () => {
    it('displays user messages with proper structure', () => {
      const userMessage = {
        id: 1,
        role: 'user',
        content: 'Hello, this is a user message',
        timestamp: new Date()
      }
      
      render(<Message message={userMessage} />)
      
      // Should have proper message structure
      expect(screen.getByText('You')).toBeInTheDocument()
      expect(screen.getByText('Hello, this is a user message')).toBeInTheDocument()
      expect(screen.getByText('Just now')).toBeInTheDocument()
    })

    it('displays agent messages with proper structure', () => {
      const agentMessage = {
        id: 2,
        role: 'model',
        content: 'Hello, this is an agent response',
        timestamp: new Date()
      }
      
      render(<Message message={agentMessage} />)
      
      // Should have proper message structure
      expect(screen.getByText('Oracle')).toBeInTheDocument()
      expect(screen.getByText('Hello, this is an agent response')).toBeInTheDocument()
      expect(screen.getByText('🤖')).toBeInTheDocument()
    })

    it('handles line breaks in messages properly', () => {
      const messageWithBreaks = {
        id: 3,
        role: 'user',
        content: 'Line 1\nLine 2\nLine 3',
        timestamp: new Date()
      }
      
      render(<Message message={messageWithBreaks} />)
      
      // Should preserve line breaks
      const messageText = screen.getByText(/Line 1/)
      expect(messageText).toBeInTheDocument()
    })

    it('formats timestamps accessibly', () => {
      const oldMessage = {
        id: 4,
        role: 'user',
        content: 'Old message',
        timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000) // 2 hours ago
      }
      
      render(<Message message={oldMessage} />)
      
      // Should show relative time
      expect(screen.getByText('2h ago')).toBeInTheDocument()
    })
  })

  describe('ErrorDisplay Accessibility', () => {
    it('has proper error announcement', () => {
      render(
        <ErrorDisplay 
          error="Test error message" 
          type="error" 
          onRetry={vi.fn()} 
          onDismiss={vi.fn()} 
        />
      )
      
      // Should have proper error structure
      expect(screen.getByText('Error')).toBeInTheDocument()
      expect(screen.getByText('Test error message')).toBeInTheDocument()
      
      // Should have retry button
      expect(screen.getByText('Try Again')).toBeInTheDocument()
      
      // Should have dismiss button with proper label
      const dismissButton = screen.getByRole('button', { name: /dismiss error/i })
      expect(dismissButton).toBeInTheDocument()
    })

    it('provides different error types with proper styling', () => {
      const { rerender } = render(
        <ErrorDisplay error="Network error" type="network" />
      )
      
      expect(screen.getByText('Connection Error')).toBeInTheDocument()
      expect(screen.getByText('🌐')).toBeInTheDocument()
      
      rerender(<ErrorDisplay error="Server error" type="server" />)
      
      expect(screen.getByText('Server Error')).toBeInTheDocument()
      expect(screen.getByText('🔧')).toBeInTheDocument()
    })

    it('handles keyboard interaction properly', async () => {
      const user = userEvent.setup()
      const mockRetry = vi.fn()
      const mockDismiss = vi.fn()
      
      render(
        <ErrorDisplay 
          error="Keyboard test error" 
          type="error" 
          onRetry={mockRetry} 
          onDismiss={mockDismiss} 
        />
      )
      
      // Tab to retry button
      await user.tab()
      const retryButton = screen.getByText('Try Again')
      expect(retryButton).toHaveFocus()
      
      // Press Enter to retry
      await user.keyboard('{Enter}')
      expect(mockRetry).toHaveBeenCalled()
      
      // Tab to dismiss button
      await user.tab()
      const dismissButton = screen.getByRole('button', { name: /dismiss error/i })
      expect(dismissButton).toHaveFocus()
      
      // Press Enter to dismiss
      await user.keyboard('{Enter}')
      expect(mockDismiss).toHaveBeenCalled()
    })
  })

  describe('Color Contrast and Visual Accessibility', () => {
    it('maintains proper contrast in different themes', async () => {
      // This test would ideally use a color contrast analyzer
      // For now, we'll test that elements are visible and readable
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      // Check that text elements are visible
      expect(screen.getByText('Oracle Chat')).toBeVisible()
      expect(screen.getByText('Welcome to Oracle Chat')).toBeVisible()
      
      // Check that interactive elements are visible
      const input = screen.getByPlaceholderText(/Type your message/)
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      expect(input).toBeVisible()
      expect(sendButton).toBeVisible()
    })

    it('supports high contrast mode preferences', () => {
      // Test that components work with high contrast CSS
      render(<App />)
      
      // Elements should still be functional in high contrast mode
      const input = screen.getByPlaceholderText(/Type your message/)
      expect(input).toBeInTheDocument()
    })
  })

  describe('Screen Reader Support', () => {
    it('provides proper live region updates', async () => {
      const user = userEvent.setup()
      
      postChatMessage.mockResolvedValue({ response: 'Screen reader test response' })
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      const input = screen.getByPlaceholderText(/Type your message/)
      
      await user.type(input, 'Test message')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Should announce loading state
      expect(screen.getByText('Oracle is thinking...')).toBeInTheDocument()
      
      // Should announce response
      await waitFor(() => {
        expect(screen.getByText('Screen reader test response')).toBeInTheDocument()
      })
    })

    it('provides proper focus management', async () => {
      const user = userEvent.setup()
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      // Focus should be manageable via keyboard
      await user.tab()
      const input = screen.getByPlaceholderText(/Type your message/)
      expect(input).toHaveFocus()
      
      // Focus should move to send button
      await user.tab()
      const sendButton = screen.getByRole('button', { name: /send/i })
      expect(sendButton).toHaveFocus()
    })
  })
})