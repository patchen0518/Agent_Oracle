// Complete user workflow tests covering full user journeys
// Based on React Testing Library user-centric testing patterns (Context 7 lookup: 2025-01-27)

import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from '../App'

// Mock the API service
vi.mock('../services/api', () => ({
  checkHealth: vi.fn(),
  postChatMessage: vi.fn()
}))

import { checkHealth, postChatMessage } from '../services/api'

describe('Complete User Workflow Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    checkHealth.mockResolvedValue({ status: 'ok' })
  })

  describe('First-Time User Experience', () => {
    it('guides new user through first conversation', async () => {
      const user = userEvent.setup()
      
      postChatMessage
        .mockResolvedValueOnce({ response: "Hello! I'm Oracle, your AI assistant. I'm here to help answer questions, provide information, and have conversations with you. What would you like to know?" })
        .mockResolvedValueOnce({ response: "I can help with a wide variety of topics including:\n\n• Answering questions about science, technology, history, and more\n• Helping with writing and creative tasks\n• Providing explanations and tutorials\n• Having general conversations\n\nWhat interests you most?" })
        .mockResolvedValueOnce({ response: "Great choice! I'd be happy to help with technology questions. You can ask me about programming languages, software development, computer science concepts, emerging technologies, or any tech-related topic. What specific area of technology are you curious about?" })
      
      render(<App />)
      
      // Wait for app to load
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      // User sees welcome screen
      expect(screen.getByText('Welcome to Oracle Chat')).toBeInTheDocument()
      expect(screen.getByText('Start a conversation by typing a message below.')).toBeInTheDocument()
      
      // User types first message
      const input = screen.getByPlaceholderText(/Type your message/)
      await user.type(input, 'Hello, what can you help me with?')
      
      // User sends message
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // User sees their message appear
      expect(screen.getByText('Hello, what can you help me with?')).toBeInTheDocument()
      
      // User sees loading indicator
      expect(screen.getByText('Oracle is thinking...')).toBeInTheDocument()
      
      // User receives response
      await waitFor(() => {
        expect(screen.getByText(/Hello! I'm Oracle, your AI assistant/)).toBeInTheDocument()
      })
      
      // User asks follow-up question
      await user.type(input, 'What topics can you help with?')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/I can help with a wide variety of topics/)).toBeInTheDocument()
      })
      
      // User shows interest in specific topic
      await user.type(input, 'I\'m interested in technology')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/Great choice! I'd be happy to help with technology/)).toBeInTheDocument()
      })
      
      // Verify conversation history is maintained
      expect(screen.getByText('Hello, what can you help me with?')).toBeInTheDocument()
      expect(screen.getByText('What topics can you help with?')).toBeInTheDocument()
      expect(screen.getByText('I\'m interested in technology')).toBeInTheDocument()
      
      // Verify API calls included proper history
      expect(postChatMessage).toHaveBeenCalledTimes(3)
      
      // First call - no history
      expect(postChatMessage).toHaveBeenNthCalledWith(1, {
        message: 'Hello, what can you help me with?',
        history: []
      })
      
      // Second call - includes first exchange
      expect(postChatMessage).toHaveBeenNthCalledWith(2, {
        message: 'What topics can you help with?',
        history: [
          { role: 'user', parts: 'Hello, what can you help me with?' },
          { role: 'model', parts: "Hello! I'm Oracle, your AI assistant. I'm here to help answer questions, provide information, and have conversations with you. What would you like to know?" }
        ]
      })
      
      // Third call - includes full conversation
      expect(postChatMessage).toHaveBeenNthCalledWith(3, {
        message: 'I\'m interested in technology',
        history: [
          { role: 'user', parts: 'Hello, what can you help me with?' },
          { role: 'model', parts: "Hello! I'm Oracle, your AI assistant. I'm here to help answer questions, provide information, and have conversations with you. What would you like to know?" },
          { role: 'user', parts: 'What topics can you help with?' },
          { role: 'model', parts: "I can help with a wide variety of topics including:\n\n• Answering questions about science, technology, history, and more\n• Helping with writing and creative tasks\n• Providing explanations and tutorials\n• Having general conversations\n\nWhat interests you most?" }
        ]
      })
    })
  })

  describe('Problem-Solving Workflow', () => {
    it('helps user solve a technical problem step by step', async () => {
      const user = userEvent.setup()
      
      postChatMessage
        .mockResolvedValueOnce({ response: "I'd be happy to help you debug your JavaScript code! Please share the code that's not working and describe what you expected it to do versus what's actually happening." })
        .mockResolvedValueOnce({ response: "I can see the issue! The problem is in line 3 where you're using `=` (assignment) instead of `===` (comparison) in your if statement. Here's the corrected code:\n\n```javascript\nfunction checkAge(age) {\n  if (age === 18) {\n    return 'You are exactly 18!';\n  }\n  return 'You are not 18';\n}\n```\n\nThe `=` operator assigns a value, while `===` compares values. This is a common mistake!" })
        .mockResolvedValueOnce({ response: "Exactly! The difference is:\n\n• `=` is assignment (sets a value)\n• `==` is loose equality (compares with type conversion)\n• `===` is strict equality (compares without type conversion)\n\nAlways use `===` for comparisons to avoid unexpected behavior. Try running your corrected code now!" })
        .mockResolvedValueOnce({ response: "Excellent! I'm glad that fixed it. This is a very common JavaScript gotcha. Some tips to avoid similar issues:\n\n1. Always use `===` and `!==` for comparisons\n2. Use a linter like ESLint to catch these errors\n3. Consider using TypeScript for better type safety\n\nIs there anything else about JavaScript you'd like to learn?" })
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      // User describes problem
      const input = screen.getByPlaceholderText(/Type your message/)
      await user.type(input, 'I have a JavaScript bug I can\'t figure out. Can you help?')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/I'd be happy to help you debug/)).toBeInTheDocument()
      })
      
      // User provides code
      const codeSnippet = `function checkAge(age) {
  if (age = 18) {
    return 'You are exactly 18!';
  }
  return 'You are not 18';
}`
      
      await user.type(input, `Here's my code:\n\n${codeSnippet}\n\nIt's supposed to check if someone is 18, but it's not working right.`)
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/I can see the issue!/)).toBeInTheDocument()
      })
      
      // User asks for clarification
      await user.type(input, 'Oh I see! Can you explain the difference between = and === ?')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/Exactly! The difference is:/)).toBeInTheDocument()
      })
      
      // User confirms solution works
      await user.type(input, 'That worked perfectly! Thank you so much.')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      await waitFor(() => {
        expect(screen.getByText(/Excellent! I'm glad that fixed it/)).toBeInTheDocument()
      })
      
      // Verify complete conversation is visible
      expect(screen.getByText('I have a JavaScript bug I can\'t figure out. Can you help?')).toBeInTheDocument()
      expect(screen.getByText(/Here's my code:/)).toBeInTheDocument()
      expect(screen.getByText('Oh I see! Can you explain the difference between = and === ?')).toBeInTheDocument()
      expect(screen.getByText('That worked perfectly! Thank you so much.')).toBeInTheDocument()
    })
  })

  describe('Error Recovery Workflow', () => {
    it('handles network issues and helps user recover', async () => {
      const user = userEvent.setup()
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      // User starts conversation successfully
      postChatMessage.mockResolvedValueOnce({ response: 'Hello! How can I help you today?' })
      
      const input = screen.getByPlaceholderText(/Type your message/)
      await user.type(input, 'Hello Oracle!')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      await waitFor(() => {
        expect(screen.getByText('Hello! How can I help you today?')).toBeInTheDocument()
      })
      
      // Network error occurs
      postChatMessage.mockRejectedValueOnce(new Error('Network error - please check your connection'))
      
      await user.type(input, 'Can you help me with coding?')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // User sees error message
      await waitFor(() => {
        expect(screen.getByText('Network error - please check your connection')).toBeInTheDocument()
      })
      
      // User message is still visible
      expect(screen.getByText('Can you help me with coding?')).toBeInTheDocument()
      
      // User tries to retry
      const retryButton = screen.getByText('Try Again')
      
      // First retry also fails
      postChatMessage.mockRejectedValueOnce(new Error('Network error - please check your connection'))
      await user.click(retryButton)
      
      await waitFor(() => {
        expect(screen.getByText('Network error - please check your connection')).toBeInTheDocument()
      })
      
      // Second retry succeeds
      postChatMessage.mockResolvedValueOnce({ response: 'Absolutely! I\'d be happy to help you with coding. What programming language or concept are you working with?' })
      
      await user.click(screen.getByText('Try Again'))
      
      await waitFor(() => {
        expect(screen.getByText('Absolutely! I\'d be happy to help you with coding')).toBeInTheDocument()
      })
      
      // Error message should be gone
      expect(screen.queryByText('Network error - please check your connection')).not.toBeInTheDocument()
      
      // Conversation continues normally
      await user.type(input, 'I\'m learning Python')
      postChatMessage.mockResolvedValueOnce({ response: 'Python is a great choice! It\'s beginner-friendly and very powerful. What aspect of Python would you like to explore?' })
      
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      await waitFor(() => {
        expect(screen.getByText('Python is a great choice!')).toBeInTheDocument()
      })
      
      // Verify full conversation history is maintained despite errors
      expect(screen.getByText('Hello Oracle!')).toBeInTheDocument()
      expect(screen.getByText('Hello! How can I help you today?')).toBeInTheDocument()
      expect(screen.getByText('Can you help me with coding?')).toBeInTheDocument()
      expect(screen.getByText('I\'m learning Python')).toBeInTheDocument()
    })
  })

  describe('Long Conversation Workflow', () => {
    it('maintains context and performance in extended conversation', async () => {
      const user = userEvent.setup()
      
      // Mock responses for a long conversation
      const responses = [
        'Hello! I\'m here to help.',
        'That\'s a great question about AI.',
        'Machine learning is indeed fascinating.',
        'Neural networks work by mimicking brain neurons.',
        'Deep learning uses multiple layers of neural networks.',
        'Yes, that\'s correct about backpropagation.',
        'Convolutional neural networks are great for images.',
        'Recurrent neural networks handle sequences well.',
        'Transformers have revolutionized NLP.',
        'GPT models are based on transformer architecture.'
      ]
      
      postChatMessage.mockImplementation(() => {
        const response = responses.shift()
        return Promise.resolve({ response: response || 'Default response' })
      })
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      const input = screen.getByPlaceholderText(/Type your message/)
      const messages = [
        'Hello, can you tell me about AI?',
        'What is machine learning?',
        'How do neural networks work?',
        'What about deep learning?',
        'Is that related to backpropagation?',
        'What are CNNs?',
        'And RNNs?',
        'What are transformers in AI?',
        'Tell me about GPT models'
      ]
      
      // Send multiple messages to build up conversation
      for (let i = 0; i < messages.length; i++) {
        await user.clear(input)
        await user.type(input, messages[i])
        await user.click(screen.getByRole('button', { name: /send/i }))
        
        // Wait for response
        await waitFor(() => {
          expect(screen.getByText(new RegExp(responses[i] || 'Default'))).toBeInTheDocument()
        }, { timeout: 2000 })
      }
      
      // Verify all messages are still visible
      expect(screen.getByText('Hello, can you tell me about AI?')).toBeInTheDocument()
      expect(screen.getByText('Tell me about GPT models')).toBeInTheDocument()
      
      // Verify conversation history was passed correctly in final call
      expect(postChatMessage).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: 'Tell me about GPT models',
          history: expect.arrayContaining([
            expect.objectContaining({ role: 'user', parts: 'Hello, can you tell me about AI?' }),
            expect.objectContaining({ role: 'model', parts: 'Hello! I\'m here to help.' })
          ])
        })
      )
      
      // Check that history has correct length (should be 16: 8 user + 8 agent messages)
      const lastCall = postChatMessage.mock.calls[postChatMessage.mock.calls.length - 1][0]
      expect(lastCall.history).toHaveLength(16)
    })
  })

  describe('Input Validation Workflow', () => {
    it('guides user through input validation and limits', async () => {
      const user = userEvent.setup()
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      const input = screen.getByPlaceholderText(/Type your message/)
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      // User tries to send empty message
      await user.click(sendButton)
      
      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText('Please enter a message')).toBeInTheDocument()
      })
      
      // User types a very long message
      const longMessage = 'This is a very long message. '.repeat(200) // About 5000 characters
      await user.type(input, longMessage)
      
      // Should show character limit warning
      await waitFor(() => {
        expect(screen.getByText(/Message too long/)).toBeInTheDocument()
      })
      
      // Send button should be disabled
      expect(sendButton).toBeDisabled()
      
      // User reduces message length
      await user.clear(input)
      const reasonableMessage = 'This is a reasonable length message that should work fine.'
      await user.type(input, reasonableMessage)
      
      // Validation error should clear
      expect(screen.queryByText(/Message too long/)).not.toBeInTheDocument()
      
      // Send button should be enabled
      expect(sendButton).toBeEnabled()
      
      // User can send message successfully
      postChatMessage.mockResolvedValueOnce({ response: 'Message received successfully!' })
      
      await user.click(sendButton)
      
      await waitFor(() => {
        expect(screen.getByText('Message received successfully!')).toBeInTheDocument()
      })
    })
  })

  describe('Keyboard Navigation Workflow', () => {
    it('supports complete keyboard-only interaction', async () => {
      const user = userEvent.setup()
      
      postChatMessage.mockResolvedValue({ response: 'Keyboard navigation works great!' })
      
      render(<App />)
      
      await waitFor(() => {
        expect(screen.getByText('Backend: connected')).toBeInTheDocument()
      })
      
      // Tab to input field
      await user.tab()
      const input = screen.getByPlaceholderText(/Type your message/)
      expect(input).toHaveFocus()
      
      // Type message using keyboard
      await user.type(input, 'Testing keyboard navigation')
      
      // Use Enter to send (instead of tabbing to button)
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(screen.getByText('Keyboard navigation works great!')).toBeInTheDocument()
      })
      
      // Test Shift+Enter for new line
      await user.type(input, 'Line 1')
      await user.keyboard('{Shift>}{Enter}{/Shift}')
      await user.type(input, 'Line 2')
      
      // Input should contain both lines
      expect(input.value).toBe('Line 1\nLine 2')
      
      // Send multi-line message
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(screen.getByText('Line 1')).toBeInTheDocument()
        expect(screen.getByText('Line 2')).toBeInTheDocument()
      })
    })
  })
})