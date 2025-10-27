// MessageInput component tests
// Based on React Testing Library best practices (Context 7 lookup: 2025-01-27)

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import MessageInput from './MessageInput'

describe('MessageInput', () => {
  const defaultProps = {
    onSendMessage: vi.fn(),
    isLoading: false,
    disabled: false
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders message input field and send button', () => {
    render(<MessageInput {...defaultProps} />)
    
    expect(screen.getByPlaceholderText(/Type your message/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
  })

  it('calls onSendMessage when form is submitted with valid message', async () => {
    const user = userEvent.setup()
    render(<MessageInput {...defaultProps} />)
    
    const input = screen.getByPlaceholderText(/Type your message/)
    const sendButton = screen.getByRole('button', { name: /send/i })
    
    await user.type(input, 'Hello, world!')
    await user.click(sendButton)
    
    expect(defaultProps.onSendMessage).toHaveBeenCalledWith('Hello, world!')
  })

  it('clears input after sending message', async () => {
    const user = userEvent.setup()
    render(<MessageInput {...defaultProps} />)
    
    const input = screen.getByPlaceholderText(/Type your message/)
    
    await user.type(input, 'Test message')
    await user.click(screen.getByRole('button', { name: /send/i }))
    
    expect(input.value).toBe('')
  })

  it('shows validation error for empty message', async () => {
    const user = userEvent.setup()
    render(<MessageInput {...defaultProps} />)
    
    const sendButton = screen.getByRole('button', { name: /send/i })
    await user.click(sendButton)
    
    expect(screen.getByText('Please enter a message')).toBeInTheDocument()
    expect(defaultProps.onSendMessage).not.toHaveBeenCalled()
  })

  it('shows validation error for message too long', async () => {
    render(<MessageInput {...defaultProps} />)
    
    const input = screen.getByPlaceholderText(/Type your message/)
    const longMessage = 'a'.repeat(4001) // Exceeds 4000 character limit
    
    // Use fireEvent for large text input to avoid timeout
    fireEvent.change(input, { target: { value: longMessage } })
    
    expect(screen.getByText(/Message too long/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
  })

  it('shows character count', async () => {
    render(<MessageInput {...defaultProps} />)
    
    const input = screen.getByPlaceholderText(/Type your message/)
    fireEvent.change(input, { target: { value: 'Hello' } })
    
    expect(screen.getByText('5/4000')).toBeInTheDocument()
  })

  it('disables input and button when disabled prop is true', () => {
    render(<MessageInput {...defaultProps} disabled={true} />)
    
    const input = screen.getByPlaceholderText(/Backend not connected/)
    const sendButton = screen.getByRole('button', { name: /send/i })
    
    expect(input).toBeDisabled()
    expect(sendButton).toBeDisabled()
  })

  it('shows loading state when isLoading is true', () => {
    render(<MessageInput {...defaultProps} isLoading={true} />)
    
    const sendButton = screen.getByRole('button', { name: /sending/i })
    expect(sendButton).toBeDisabled()
  })

  it('sends message on Enter key press', async () => {
    render(<MessageInput {...defaultProps} />)
    
    const input = screen.getByPlaceholderText(/Type your message/)
    
    // Set the value directly and then trigger keypress
    fireEvent.change(input, { target: { value: 'Test message' } })
    fireEvent.keyPress(input, { key: 'Enter', code: 'Enter', charCode: 13 })
    
    expect(defaultProps.onSendMessage).toHaveBeenCalledWith('Test message')
  })

  it('does not send message on Shift+Enter', async () => {
    const user = userEvent.setup()
    render(<MessageInput {...defaultProps} />)
    
    const input = screen.getByPlaceholderText(/Type your message/)
    
    await user.type(input, 'Test message')
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    
    expect(defaultProps.onSendMessage).not.toHaveBeenCalled()
  })
})