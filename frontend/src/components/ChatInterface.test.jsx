// ChatInterface component tests
// Based on React Testing Library best practices (Context 7 lookup: 2025-01-27)

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import ChatInterface from './ChatInterface'

describe('ChatInterface', () => {
  const mockMessages = [
    {
      id: 1,
      role: 'user',
      content: 'Hello, how are you?',
      timestamp: new Date('2025-01-27T10:00:00Z'),
      session_id: 1
    },
    {
      id: 2,
      role: 'assistant',
      content: 'I am doing well, thank you for asking!',
      timestamp: new Date('2025-01-27T10:00:30Z'),
      session_id: 1
    }
  ]

  const defaultProps = {
    sessionId: null,
    messages: [],
    isLoading: false,
    onLoadMessages: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders empty state when no session is selected', () => {
    render(<ChatInterface {...defaultProps} />)
    
    expect(screen.getByText('This is Oracle')).toBeInTheDocument()
    expect(screen.getByText('Create or select a session to start chatting.')).toBeInTheDocument()
  })

  it('renders empty state for selected session with no messages', () => {
    render(<ChatInterface {...defaultProps} sessionId={1} />)
    
    expect(screen.getByText('This is Oracle')).toBeInTheDocument()
    expect(screen.getByText('Start a conversation in this session by typing a message below.')).toBeInTheDocument()
  })

  it('renders messages when provided', () => {
    render(<ChatInterface {...defaultProps} sessionId={1} messages={mockMessages} />)
    
    expect(screen.getByText('Hello, how are you?')).toBeInTheDocument()
    expect(screen.getByText('I am doing well, thank you for asking!')).toBeInTheDocument()
  })

  it('calls onLoadMessages when sessionId changes', async () => {
    const onLoadMessages = vi.fn().mockResolvedValue()
    const { rerender } = render(<ChatInterface {...defaultProps} onLoadMessages={onLoadMessages} />)
    
    expect(onLoadMessages).not.toHaveBeenCalled()
    
    rerender(<ChatInterface {...defaultProps} sessionId={1} onLoadMessages={onLoadMessages} />)
    
    expect(onLoadMessages).toHaveBeenCalledWith(1)
  })

  it('shows loading messages indicator when loading session messages', () => {
    const onLoadMessages = vi.fn().mockImplementation(() => new Promise(() => {})) // Never resolves
    render(<ChatInterface {...defaultProps} sessionId={1} onLoadMessages={onLoadMessages} />)
    
    expect(screen.getByText('Loading conversation history...')).toBeInTheDocument()
  })

  it('shows loading indicator when isLoading is true', () => {
    render(<ChatInterface {...defaultProps} sessionId={1} isLoading={true} />)
    
    expect(screen.getByText('Oracle is thinking...')).toBeInTheDocument()
    // Check for typing indicator by class
    const typingIndicator = document.querySelector('.typing-indicator')
    expect(typingIndicator).toBeInTheDocument()
  })

  it('does not call onLoadMessages when sessionId is null', () => {
    const onLoadMessages = vi.fn()
    render(<ChatInterface {...defaultProps} sessionId={null} onLoadMessages={onLoadMessages} />)
    
    expect(onLoadMessages).not.toHaveBeenCalled()
  })

  it('handles onLoadMessages error gracefully', async () => {
    const onLoadMessages = vi.fn().mockImplementation(() => Promise.reject(new Error('Failed to load')))
    render(<ChatInterface {...defaultProps} sessionId={1} onLoadMessages={onLoadMessages} />)
    
    await waitFor(() => {
      expect(onLoadMessages).toHaveBeenCalledWith(1)
    })
    
    // Should not crash and loading should complete
    await waitFor(() => {
      expect(screen.queryByText('Loading conversation history...')).not.toBeInTheDocument()
    })
  })

  it('renders many messages correctly', () => {
    const manyMessages = Array.from({ length: 5 }, (_, i) => ({
      id: i + 1,
      role: i % 2 === 0 ? 'user' : 'assistant',
      content: `Message ${i + 1}`,
      timestamp: new Date(),
      session_id: 1
    }))
    
    render(<ChatInterface {...defaultProps} sessionId={1} messages={manyMessages} />)
    
    expect(screen.getByText('Message 1')).toBeInTheDocument()
    expect(screen.getByText('Message 5')).toBeInTheDocument()
  })

  it('renders few messages correctly', () => {
    render(<ChatInterface {...defaultProps} sessionId={1} messages={mockMessages} />)
    
    expect(screen.getByText('Hello, how are you?')).toBeInTheDocument()
    expect(screen.getByText('I am doing well, thank you for asking!')).toBeInTheDocument()
  })

  it('renders both loading and messages when loading with existing messages', () => {
    render(<ChatInterface {...defaultProps} sessionId={1} messages={mockMessages} isLoading={true} />)
    
    expect(screen.getByText('Hello, how are you?')).toBeInTheDocument()
    expect(screen.getByText('I am doing well, thank you for asking!')).toBeInTheDocument()
    expect(screen.getByText('Oracle is thinking...')).toBeInTheDocument()
  })

  it('loads messages only once per session change', async () => {
    const onLoadMessages = vi.fn().mockResolvedValue()
    const { rerender } = render(<ChatInterface {...defaultProps} sessionId={1} onLoadMessages={onLoadMessages} />)
    
    await waitFor(() => {
      expect(onLoadMessages).toHaveBeenCalledTimes(1)
    })
    
    // Re-render with same sessionId should not trigger another load
    rerender(<ChatInterface {...defaultProps} sessionId={1} onLoadMessages={onLoadMessages} />)
    
    expect(onLoadMessages).toHaveBeenCalledTimes(1)
    
    // Change sessionId should trigger another load
    rerender(<ChatInterface {...defaultProps} sessionId={2} onLoadMessages={onLoadMessages} />)
    
    await waitFor(() => {
      expect(onLoadMessages).toHaveBeenCalledTimes(2)
      expect(onLoadMessages).toHaveBeenLastCalledWith(2)
    })
  })
})