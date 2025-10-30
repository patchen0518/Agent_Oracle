// SessionHeader component tests
// Based on React Testing Library best practices

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import SessionHeader from './SessionHeader'

describe('SessionHeader', () => {
  const mockSession = {
    id: 1,
    title: 'Test Session',
    message_count: 5,
    created_at: '2025-01-27T10:00:00Z',
    updated_at: '2025-01-27T11:00:00Z'
  }

  const defaultProps = {
    session: null,
    onSessionUpdate: vi.fn(),
    onSessionDelete: vi.fn(),
    onToggleSidebar: vi.fn(),
    backendStatus: 'connected'
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders no-session state when session is null', () => {
    render(<SessionHeader {...defaultProps} />)
    
    expect(screen.getByText('Oracle')).toBeInTheDocument()
    expect(screen.getByText('Select a session to start chatting')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /toggle sidebar/i })).toBeInTheDocument()
  })

  it('renders session information when session is provided', () => {
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    expect(screen.getByText('Test Session')).toBeInTheDocument()
    expect(screen.getByText('5 messages')).toBeInTheDocument()
    expect(screen.getByText(/Created/)).toBeInTheDocument()
    expect(screen.getByText(/Updated/)).toBeInTheDocument()
  })

  it('calls onToggleSidebar when sidebar toggle is clicked', async () => {
    const user = userEvent.setup()
    render(<SessionHeader {...defaultProps} />)
    
    const toggleButton = screen.getByRole('button', { name: /toggle sidebar/i })
    await user.click(toggleButton)
    
    expect(defaultProps.onToggleSidebar).toHaveBeenCalledTimes(1)
  })

  it('shows backend status correctly', () => {
    render(<SessionHeader {...defaultProps} backendStatus="disconnected" />)
    
    expect(screen.getByText('Backend: disconnected')).toBeInTheDocument()
  })

  it('enters edit mode when session title is clicked', async () => {
    const user = userEvent.setup()
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    const titleElement = screen.getByText('Test Session')
    await user.click(titleElement)
    
    expect(screen.getByDisplayValue('Test Session')).toBeInTheDocument()
    expect(screen.getByTitle('Save title')).toBeInTheDocument()
    expect(screen.getByTitle('Cancel editing')).toBeInTheDocument()
  })

  it('saves title when save button is clicked', async () => {
    const user = userEvent.setup()
    defaultProps.onSessionUpdate.mockResolvedValue()
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    // Enter edit mode
    await user.click(screen.getByText('Test Session'))
    
    // Edit title
    const input = screen.getByDisplayValue('Test Session')
    await user.clear(input)
    await user.type(input, 'Updated Session Title')
    
    // Save
    await user.click(screen.getByTitle('Save title'))
    
    expect(defaultProps.onSessionUpdate).toHaveBeenCalledWith(1, { title: 'Updated Session Title' })
  })

  it('cancels editing when cancel button is clicked', async () => {
    const user = userEvent.setup()
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    // Enter edit mode
    await user.click(screen.getByText('Test Session'))
    
    // Edit title using fireEvent to avoid blur
    const input = screen.getByDisplayValue('Test Session')
    fireEvent.change(input, { target: { value: 'Changed Title' } })
    
    // Cancel
    await user.click(screen.getByTitle('Cancel editing'))
    
    // Should show original title
    expect(screen.getByText('Test Session')).toBeInTheDocument()
    expect(defaultProps.onSessionUpdate).not.toHaveBeenCalled()
  })

  it('saves title on Enter key press', async () => {
    const user = userEvent.setup()
    defaultProps.onSessionUpdate.mockResolvedValue()
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    // Enter edit mode
    await user.click(screen.getByText('Test Session'))
    
    // Edit and press Enter
    const input = screen.getByDisplayValue('Test Session')
    await user.clear(input)
    await user.type(input, 'New Title{Enter}')
    
    expect(defaultProps.onSessionUpdate).toHaveBeenCalledWith(1, { title: 'New Title' })
  })

  it('cancels editing on Escape key press', async () => {
    const user = userEvent.setup()
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    // Enter edit mode
    await user.click(screen.getByText('Test Session'))
    
    // Press Escape
    const input = screen.getByDisplayValue('Test Session')
    await user.type(input, '{Escape}')
    
    // Should exit edit mode
    expect(screen.getByText('Test Session')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('Test Session')).not.toBeInTheDocument()
  })

  it('shows delete confirmation modal when delete button is clicked', async () => {
    const user = userEvent.setup()
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    const deleteButton = screen.getByTitle('Delete session')
    await user.click(deleteButton)
    
    expect(screen.getByRole('heading', { name: 'Delete Session' })).toBeInTheDocument()
    expect(screen.getByText(/Are you sure you want to delete/)).toBeInTheDocument()
    expect(screen.getByText('"Test Session"')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete session/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
  })

  it('deletes session when confirmed in modal', async () => {
    const user = userEvent.setup()
    defaultProps.onSessionDelete.mockResolvedValue()
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    // Open delete modal
    await user.click(screen.getByTitle('Delete session'))
    
    // Confirm deletion
    await user.click(screen.getByRole('button', { name: /delete session/i }))
    
    expect(defaultProps.onSessionDelete).toHaveBeenCalledWith(1)
  })

  it('cancels deletion when cancel is clicked in modal', async () => {
    const user = userEvent.setup()
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    // Open delete modal
    await user.click(screen.getByTitle('Delete session'))
    
    // Cancel deletion
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    
    expect(screen.queryByText('Delete Session')).not.toBeInTheDocument()
    expect(defaultProps.onSessionDelete).not.toHaveBeenCalled()
  })

  it('closes modal when clicking overlay', async () => {
    const user = userEvent.setup()
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    // Open delete modal
    await user.click(screen.getByTitle('Delete session'))
    
    // Click overlay
    const overlay = document.querySelector('.modal-overlay')
    await user.click(overlay)
    
    expect(screen.queryByText('Delete Session')).not.toBeInTheDocument()
  })

  it('does not save empty title', async () => {
    const user = userEvent.setup()
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    // Enter edit mode
    await user.click(screen.getByText('Test Session'))
    
    // Clear title
    const input = screen.getByDisplayValue('Test Session')
    await user.clear(input)
    
    // Try to save
    await user.click(screen.getByTitle('Save title'))
    
    expect(defaultProps.onSessionUpdate).not.toHaveBeenCalled()
  })

  it('handles session update error gracefully', async () => {
    const user = userEvent.setup()
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    defaultProps.onSessionUpdate.mockRejectedValue(new Error('Update failed'))
    
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    // Enter edit mode and try to save
    await user.click(screen.getByText('Test Session'))
    const input = screen.getByDisplayValue('Test Session')
    await user.clear(input)
    await user.type(input, 'New Title')
    await user.click(screen.getByTitle('Save title'))
    
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Failed to update session title:', expect.any(Error))
    })
    
    // Should reset to original title
    expect(screen.getByDisplayValue('Test Session')).toBeInTheDocument()
    
    consoleSpy.mockRestore()
  })

  it('formats timestamps correctly', () => {
    const sessionWithSameTimestamp = {
      ...mockSession,
      created_at: '2025-01-27T10:00:00Z',
      updated_at: '2025-01-27T10:00:00Z'
    }
    
    render(<SessionHeader {...defaultProps} session={sessionWithSameTimestamp} />)
    
    // Should only show created date when created and updated are the same
    expect(screen.getByText(/Created/)).toBeInTheDocument()
    expect(screen.queryByText(/Updated/)).not.toBeInTheDocument()
  })

  it('disables controls when operations are in progress', async () => {
    const user = userEvent.setup()
    // Mock a slow update
    defaultProps.onSessionUpdate.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)))
    
    render(<SessionHeader {...defaultProps} session={mockSession} />)
    
    // Enter edit mode and start saving
    await user.click(screen.getByText('Test Session'))
    const input = screen.getByDisplayValue('Test Session')
    await user.clear(input)
    await user.type(input, 'New Title')
    
    const saveButton = screen.getByTitle('Save title')
    await user.click(saveButton)
    
    // Buttons should be disabled during update
    expect(screen.getByTitle('Save title')).toBeDisabled()
    expect(screen.getByTitle('Cancel editing')).toBeDisabled()
  })
})