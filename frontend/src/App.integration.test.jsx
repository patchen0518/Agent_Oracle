// App integration tests with API mocking
// Based on React Testing Library best practices (Context 7 lookup: 2025-01-27)

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from './App'

// Mock the API service
vi.mock('./services/api', () => ({
  checkHealth: vi.fn(),
  postChatMessage: vi.fn()
}))

import { checkHealth, postChatMessage } from './services/api'

describe('App Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default successful health check
    checkHealth.mockResolvedValue({ status: 'ok' })
  })

  it('sends a message and displays response', async () => {
    const user = userEvent.setup()
    
    // Mock successful API response
    postChatMessage.mockResolvedValue({
      response: 'Hello! How can I help you today?'
    })
    
    render(<App />)
    
    // Wait for health check to complete
    await waitFor(() => {
      expect(screen.getByText('Backend: connected')).toBeInTheDocument()
    })
    
    // Type a message
    const input = screen.getByPlaceholderText(/Type your message/)
    await user.type(input, 'Hello, Oracle!')
    
    // Send the message
    const sendButton = screen.getByRole('button', { name: /send/i })
    await user.click(sendButton)
    
    // Check that user message appears
    expect(screen.getByText('Hello, Oracle!')).toBeInTheDocument()
    
    // Wait for API response to appear
    await waitFor(() => {
      expect(screen.getByText('Hello! How can I help you today?')).toBeInTheDocument()
    })
    
    // Verify API was called with correct data
    expect(postChatMessage).toHaveBeenCalledWith({
      message: 'Hello, Oracle!',
      history: []
    })
  })

  it('maintains conversation history across multiple messages', async () => {
    const user = userEvent.setup()
    
    // Mock API responses
    postChatMessage
      .mockResolvedValueOnce({ response: 'Nice to meet you!' })
      .mockResolvedValueOnce({ response: 'I am an AI assistant.' })
    
    render(<App />)
    
    // Wait for health check
    await waitFor(() => {
      expect(screen.getByText('Backend: connected')).toBeInTheDocument()
    })
    
    const input = screen.getByPlaceholderText(/Type your message/)
    const sendButton = screen.getByRole('button', { name: /send/i })
    
    // Send first message
    await user.type(input, 'Hello!')
    await user.click(sendButton)
    
    await waitFor(() => {
      expect(screen.getByText('Nice to meet you!')).toBeInTheDocument()
    })
    
    // Send second message
    await user.type(input, 'What are you?')
    await user.click(sendButton)
    
    await waitFor(() => {
      expect(screen.getByText('I am an AI assistant.')).toBeInTheDocument()
    })
    
    // Verify second API call includes conversation history
    expect(postChatMessage).toHaveBeenLastCalledWith({
      message: 'What are you?',
      history: [
        { role: 'user', parts: 'Hello!' },
        { role: 'model', parts: 'Nice to meet you!' }
      ]
    })
  })

  it('displays error message when API call fails', async () => {
    const user = userEvent.setup()
    
    // Mock API failure
    postChatMessage.mockRejectedValue(new Error('Network error - please check your connection'))
    
    render(<App />)
    
    // Wait for health check
    await waitFor(() => {
      expect(screen.getByText('Backend: connected')).toBeInTheDocument()
    })
    
    // Send a message
    const input = screen.getByPlaceholderText(/Type your message/)
    await user.type(input, 'Hello!')
    await user.click(screen.getByRole('button', { name: /send/i }))
    
    // Wait for error to appear
    await waitFor(() => {
      expect(screen.getByText('Failed to send message. Please try again.')).toBeInTheDocument()
    })
    
    // User message should still be displayed
    expect(screen.getByText('Hello!')).toBeInTheDocument()
  })

  it('shows loading state during API call', async () => {
    const user = userEvent.setup()
    
    // Mock delayed API response
    let resolvePromise
    const delayedPromise = new Promise((resolve) => {
      resolvePromise = resolve
    })
    postChatMessage.mockReturnValue(delayedPromise)
    
    render(<App />)
    
    // Wait for health check
    await waitFor(() => {
      expect(screen.getByText('Backend: connected')).toBeInTheDocument()
    })
    
    // Send a message
    const input = screen.getByPlaceholderText(/Type your message/)
    await user.type(input, 'Hello!')
    await user.click(screen.getByRole('button', { name: /send/i }))
    
    // Check loading state
    expect(screen.getByText('Oracle is thinking...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled()
    
    // Resolve the promise
    resolvePromise({ response: 'Hello there!' })
    
    // Wait for loading to disappear
    await waitFor(() => {
      expect(screen.queryByText('Oracle is thinking...')).not.toBeInTheDocument()
    })
  })

  it('disables input when backend is disconnected', async () => {
    // Mock health check failure
    checkHealth.mockRejectedValue(new Error('Backend unavailable'))
    
    render(<App />)
    
    // Wait for health check to fail
    await waitFor(() => {
      expect(screen.getByText('Backend: disconnected')).toBeInTheDocument()
    })
    
    // Check that input is disabled
    const input = screen.getByPlaceholderText(/Backend not connected/)
    const sendButton = screen.getByRole('button', { name: /send/i })
    
    expect(input).toBeDisabled()
    expect(sendButton).toBeDisabled()
  })

  it('clears error when dismiss button is clicked', async () => {
    const user = userEvent.setup()
    
    // Mock API failure
    postChatMessage.mockRejectedValue(new Error('Test error'))
    
    render(<App />)
    
    // Wait for health check
    await waitFor(() => {
      expect(screen.getByText('Backend: connected')).toBeInTheDocument()
    })
    
    // Send a message to trigger error
    const input = screen.getByPlaceholderText(/Type your message/)
    await user.type(input, 'Hello!')
    await user.click(screen.getByRole('button', { name: /send/i }))
    
    // Wait for error to appear
    await waitFor(() => {
      expect(screen.getByText('Failed to send message. Please try again.')).toBeInTheDocument()
    })
    
    // Click dismiss button
    const dismissButton = screen.getByRole('button', { name: /dismiss error/i })
    await user.click(dismissButton)
    
    // Error should be gone
    expect(screen.queryByText('Failed to send message. Please try again.')).not.toBeInTheDocument()
  })
})