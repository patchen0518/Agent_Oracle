// ChatInterface component tests
// Based on React Testing Library best practices (Context 7 lookup: 2025-01-27)

import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import ChatInterface from './ChatInterface'

describe('ChatInterface', () => {
  const mockMessages = [
    {
      id: 1,
      role: 'user',
      content: 'Hello, how are you?',
      timestamp: new Date('2025-01-27T10:00:00Z')
    },
    {
      id: 2,
      role: 'model',
      content: 'I am doing well, thank you for asking!',
      timestamp: new Date('2025-01-27T10:00:30Z')
    }
  ]

  const defaultProps = {
    messages: [],
    isLoading: false,
    error: null,
    onClearError: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders empty state when no messages', () => {
    render(<ChatInterface {...defaultProps} />)
    
    expect(screen.getByText('Welcome to Oracle Chat')).toBeInTheDocument()
    expect(screen.getByText('Start a conversation by typing a message below.')).toBeInTheDocument()
  })

  it('renders messages when provided', () => {
    render(<ChatInterface {...defaultProps} messages={mockMessages} />)
    
    expect(screen.getByText('Hello, how are you?')).toBeInTheDocument()
    expect(screen.getByText('I am doing well, thank you for asking!')).toBeInTheDocument()
  })

  it('shows loading indicator when isLoading is true', () => {
    render(<ChatInterface {...defaultProps} isLoading={true} />)
    
    expect(screen.getByText('Oracle is thinking...')).toBeInTheDocument()
    // Check for typing indicator by class
    const typingIndicator = document.querySelector('.typing-indicator')
    expect(typingIndicator).toBeInTheDocument()
  })

  it('displays error banner when error is provided', () => {
    const errorMessage = 'Failed to send message'
    render(<ChatInterface {...defaultProps} error={errorMessage} />)
    
    expect(screen.getByText(errorMessage)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /dismiss error/i })).toBeInTheDocument()
  })

  it('calls onClearError when error dismiss button is clicked', async () => {
    const user = userEvent.setup()
    const errorMessage = 'Failed to send message'
    render(<ChatInterface {...defaultProps} error={errorMessage} />)
    
    const dismissButton = screen.getByRole('button', { name: /dismiss error/i })
    await user.click(dismissButton)
    
    expect(defaultProps.onClearError).toHaveBeenCalledTimes(1)
  })

  it('shows scroll to bottom button when there are many messages', () => {
    const manyMessages = Array.from({ length: 5 }, (_, i) => ({
      id: i + 1,
      role: i % 2 === 0 ? 'user' : 'model',
      content: `Message ${i + 1}`,
      timestamp: new Date()
    }))
    
    render(<ChatInterface {...defaultProps} messages={manyMessages} />)
    
    expect(screen.getByRole('button', { name: /scroll to bottom/i })).toBeInTheDocument()
  })

  it('does not show scroll to bottom button with few messages', () => {
    render(<ChatInterface {...defaultProps} messages={mockMessages} />)
    
    expect(screen.queryByRole('button', { name: /scroll to bottom/i })).not.toBeInTheDocument()
  })

  it('renders both loading and messages when loading with existing messages', () => {
    render(<ChatInterface {...defaultProps} messages={mockMessages} isLoading={true} />)
    
    expect(screen.getByText('Hello, how are you?')).toBeInTheDocument()
    expect(screen.getByText('I am doing well, thank you for asking!')).toBeInTheDocument()
    expect(screen.getByText('Oracle is thinking...')).toBeInTheDocument()
  })
})