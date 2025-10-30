// SessionSidebar component tests
// Based on React Testing Library best practices

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import SessionSidebar from './SessionSidebar'

describe('SessionSidebar', () => {
  const mockSessions = [
    {
      id: 1,
      title: 'First Session',
      message_count: 5,
      created_at: '2025-01-27T10:00:00Z',
      updated_at: '2025-01-27T11:00:00Z'
    },
    {
      id: 2,
      title: 'Second Session',
      message_count: 3,
      created_at: '2025-01-27T09:00:00Z',
      updated_at: '2025-01-27T09:30:00Z'
    }
  ]

  const defaultProps = {
    sessions: [],
    activeSessionId: null,
    onSessionSelect: vi.fn(),
    onSessionCreate: vi.fn(),
    onSessionDelete: vi.fn(),
    isLoading: false,
    isCollapsed: false,
    onToggleCollapse: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Mock window.confirm for delete tests
    window.confirm = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders sidebar header with title and collapse button', () => {
    render(<SessionSidebar {...defaultProps} />)
    
    expect(screen.getByText('Sessions')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /collapse sidebar/i })).toBeInTheDocument()
  })

  it('renders new session button when not collapsed', () => {
    render(<SessionSidebar {...defaultProps} />)
    
    expect(screen.getByRole('button', { name: /new session/i })).toBeInTheDocument()
  })

  it('does not render new session button when collapsed', () => {
    render(<SessionSidebar {...defaultProps} isCollapsed={true} />)
    
    expect(screen.queryByRole('button', { name: /new session/i })).not.toBeInTheDocument()
    expect(screen.queryByText('Sessions')).not.toBeInTheDocument()
  })

  it('calls onToggleCollapse when collapse button is clicked', async () => {
    const user = userEvent.setup()
    render(<SessionSidebar {...defaultProps} />)
    
    const collapseButton = screen.getByRole('button', { name: /collapse sidebar/i })
    await user.click(collapseButton)
    
    expect(defaultProps.onToggleCollapse).toHaveBeenCalledTimes(1)
  })

  it('shows empty state when no sessions', () => {
    render(<SessionSidebar {...defaultProps} />)
    
    expect(screen.getByText('No sessions yet')).toBeInTheDocument()
    expect(screen.getByText('Create your first session to get started')).toBeInTheDocument()
  })

  it('shows loading state when isLoading is true', () => {
    render(<SessionSidebar {...defaultProps} isLoading={true} />)
    
    expect(screen.getByText('Loading sessions...')).toBeInTheDocument()
    expect(document.querySelector('.loading-spinner')).toBeInTheDocument()
  })

  it('renders session list with metadata', () => {
    render(<SessionSidebar {...defaultProps} sessions={mockSessions} />)
    
    expect(screen.getByText('First Session')).toBeInTheDocument()
    expect(screen.getByText('Second Session')).toBeInTheDocument()
    expect(screen.getByText('5 messages')).toBeInTheDocument()
    expect(screen.getByText('3 messages')).toBeInTheDocument()
  })

  it('highlights active session', () => {
    render(<SessionSidebar {...defaultProps} sessions={mockSessions} activeSessionId={1} />)
    
    const activeSession = screen.getByText('First Session').closest('.session-item')
    expect(activeSession).toHaveClass('active')
  })

  it('calls onSessionSelect when session is clicked', async () => {
    const user = userEvent.setup()
    render(<SessionSidebar {...defaultProps} sessions={mockSessions} />)
    
    const sessionItem = screen.getByText('First Session')
    await user.click(sessionItem)
    
    expect(defaultProps.onSessionSelect).toHaveBeenCalledWith(1)
  })

  it('shows create session form when new session button is clicked', async () => {
    const user = userEvent.setup()
    render(<SessionSidebar {...defaultProps} />)
    
    const newSessionButton = screen.getByRole('button', { name: /new session/i })
    await user.click(newSessionButton)
    
    expect(screen.getByPlaceholderText('Session title...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
  })

  it('creates session when form is submitted', async () => {
    const user = userEvent.setup()
    defaultProps.onSessionCreate.mockResolvedValue()
    render(<SessionSidebar {...defaultProps} />)
    
    // Open create form
    await user.click(screen.getByRole('button', { name: /new session/i }))
    
    // Fill in title and submit
    const titleInput = screen.getByPlaceholderText('Session title...')
    await user.type(titleInput, 'New Test Session')
    await user.click(screen.getByRole('button', { name: /create/i }))
    
    expect(defaultProps.onSessionCreate).toHaveBeenCalledWith('New Test Session')
  })

  it('cancels session creation when cancel button is clicked', async () => {
    const user = userEvent.setup()
    render(<SessionSidebar {...defaultProps} />)
    
    // Open create form
    await user.click(screen.getByRole('button', { name: /new session/i }))
    
    // Cancel
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    
    expect(screen.queryByPlaceholderText('Session title...')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /new session/i })).toBeInTheDocument()
  })

  it('does not create session with empty title', async () => {
    const user = userEvent.setup()
    render(<SessionSidebar {...defaultProps} />)
    
    // Open create form
    await user.click(screen.getByRole('button', { name: /new session/i }))
    
    // Try to submit without title
    const createButton = screen.getByRole('button', { name: /create/i })
    expect(createButton).toBeDisabled()
    
    expect(defaultProps.onSessionCreate).not.toHaveBeenCalled()
  })

  it('shows delete button on session hover and handles deletion', async () => {
    const user = userEvent.setup()
    window.confirm.mockReturnValue(true)
    render(<SessionSidebar {...defaultProps} sessions={mockSessions} />)
    
    const deleteButton = screen.getAllByTitle('Delete session')[0]
    await user.click(deleteButton)
    
    expect(window.confirm).toHaveBeenCalledWith(
      'Are you sure you want to delete "First Session"? This action cannot be undone.'
    )
    expect(defaultProps.onSessionDelete).toHaveBeenCalledWith(1)
  })

  it('does not delete session when confirmation is cancelled', async () => {
    const user = userEvent.setup()
    window.confirm.mockReturnValue(false)
    render(<SessionSidebar {...defaultProps} sessions={mockSessions} />)
    
    const deleteButton = screen.getAllByTitle('Delete session')[0]
    await user.click(deleteButton)
    
    expect(window.confirm).toHaveBeenCalled()
    expect(defaultProps.onSessionDelete).not.toHaveBeenCalled()
  })

  it('formats timestamps correctly', () => {
    const recentSession = {
      id: 1,
      title: 'Recent Session',
      message_count: 1,
      created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 minutes ago
      updated_at: new Date(Date.now() - 30 * 60 * 1000).toISOString()
    }
    
    render(<SessionSidebar {...defaultProps} sessions={[recentSession]} />)
    
    expect(screen.getByText('30m ago')).toBeInTheDocument()
  })

  it('handles session creation error gracefully', async () => {
    const user = userEvent.setup()
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    defaultProps.onSessionCreate.mockRejectedValue(new Error('Creation failed'))
    
    render(<SessionSidebar {...defaultProps} />)
    
    // Open create form and submit
    await user.click(screen.getByRole('button', { name: /new session/i }))
    const titleInput = screen.getByPlaceholderText('Session title...')
    await user.type(titleInput, 'Test Session')
    await user.click(screen.getByRole('button', { name: /create/i }))
    
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Failed to create session:', expect.any(Error))
    })
    
    consoleSpy.mockRestore()
  })
})