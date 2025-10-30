// SessionLayout component tests
// Based on React Testing Library best practices

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import SessionLayout from './SessionLayout'

// Mock child components with minimal functionality
vi.mock('./SessionSidebar', () => ({
  default: ({ onSessionSelect, onToggleCollapse, isCollapsed, sessions, activeSessionId }) => (
    <div data-testid="session-sidebar" className={isCollapsed ? 'collapsed' : 'expanded'}>
      <div>Sessions: {sessions.length}</div>
      <div>Active: {activeSessionId}</div>
      <button onClick={() => onSessionSelect(1)}>Select Session 1</button>
      <button onClick={onToggleCollapse}>
        {isCollapsed ? 'Expand' : 'Collapse'}
      </button>
    </div>
  )
}))

vi.mock('./SessionHeader', () => ({
  default: ({ onToggleSidebar, session }) => (
    <div data-testid="session-header">
      <div>Current Session: {session?.title || 'None'}</div>
      <button onClick={onToggleSidebar}>Toggle Sidebar</button>
    </div>
  )
}))

describe('SessionLayout', () => {
  const mockSessions = [
    { id: 1, title: 'Session 1', message_count: 5 },
    { id: 2, title: 'Session 2', message_count: 3 }
  ]

  const defaultProps = {
    sessions: mockSessions,
    activeSession: mockSessions[0],
    onSessionSelect: vi.fn(),
    onSessionCreate: vi.fn(),
    onSessionDelete: vi.fn(),
    onSessionUpdate: vi.fn(),
    isLoading: false,
    backendStatus: 'connected'
  }

  // Mock window.innerWidth for mobile detection
  const mockInnerWidth = (width) => {
    act(() => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: width,
      })
      window.dispatchEvent(new Event('resize'))
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Default to desktop width
    mockInnerWidth(1024)
  })

  afterEach(() => {
    // Clean up body styles
    document.body.style.overflow = ''
  })

  it('renders sidebar and header components', () => {
    render(<SessionLayout {...defaultProps} />)
    
    expect(screen.getByTestId('session-sidebar')).toBeInTheDocument()
    expect(screen.getByTestId('session-header')).toBeInTheDocument()
  })

  it('renders children in content area', () => {
    render(
      <SessionLayout {...defaultProps}>
        <div data-testid="chat-content">Chat Interface</div>
      </SessionLayout>
    )
    
    expect(screen.getByTestId('chat-content')).toBeInTheDocument()
  })

  it('applies desktop layout class by default', () => {
    render(<SessionLayout {...defaultProps} />)
    
    const layout = document.querySelector('.session-layout')
    expect(layout).toHaveClass('desktop')
  })

  it('applies mobile layout class on small screens', async () => {
    render(<SessionLayout {...defaultProps} />)
    
    mockInnerWidth(600)
    
    await waitFor(() => {
      const layout = document.querySelector('.session-layout')
      expect(layout).toHaveClass('mobile')
    })
  })

  it('toggles sidebar collapse on desktop', async () => {
    const user = userEvent.setup()
    render(<SessionLayout {...defaultProps} />)
    
    const toggleButton = screen.getByText('Toggle Sidebar')
    await user.click(toggleButton)
    
    // Should show collapsed state
    expect(screen.getByText('Expand')).toBeInTheDocument()
  })

  it('passes correct props to child components', () => {
    render(<SessionLayout {...defaultProps} />)
    
    expect(screen.getByText('Sessions: 2')).toBeInTheDocument()
    expect(screen.getByText('Active: 1')).toBeInTheDocument()
    expect(screen.getByText('Current Session: Session 1')).toBeInTheDocument()
  })

  it('calls onSessionSelect when session is selected', async () => {
    const user = userEvent.setup()
    render(<SessionLayout {...defaultProps} />)
    
    const sessionButton = screen.getByText('Select Session 1')
    await user.click(sessionButton)
    
    expect(defaultProps.onSessionSelect).toHaveBeenCalledWith(1)
  })

  it('shows mobile sidebar indicator on mobile with sessions', async () => {
    render(<SessionLayout {...defaultProps} />)
    
    mockInnerWidth(600)
    
    await waitFor(() => {
      expect(screen.getByText('Sessions')).toBeInTheDocument()
      expect(screen.getByText('2')).toBeInTheDocument() // session count
    })
  })

  it('does not show mobile sidebar indicator when no sessions', async () => {
    render(<SessionLayout {...defaultProps} sessions={[]} />)
    
    mockInnerWidth(600)
    
    await waitFor(() => {
      expect(screen.queryByText('Sessions')).not.toBeInTheDocument()
    })
  })

  it('handles mobile layout class switching', async () => {
    render(<SessionLayout {...defaultProps} />)
    
    // Start with desktop
    await waitFor(() => {
      expect(document.querySelector('.session-layout')).toHaveClass('desktop')
    })
    
    // Switch to mobile
    mockInnerWidth(600)
    
    await waitFor(() => {
      expect(document.querySelector('.session-layout')).toHaveClass('mobile')
    })
  })

  it('toggles sidebar collapse state on desktop', async () => {
    const user = userEvent.setup()
    render(<SessionLayout {...defaultProps} />)
    
    // Should start with expanded sidebar
    expect(screen.getByText('Collapse')).toBeInTheDocument()
    
    // Click toggle to collapse
    const toggleButton = screen.getByText('Toggle Sidebar')
    await user.click(toggleButton)
    
    // Should show expand button (sidebar is collapsed)
    expect(screen.getByText('Expand')).toBeInTheDocument()
  })

  it('handles responsive layout changes', async () => {
    render(<SessionLayout {...defaultProps} />)
    
    // Start with desktop
    await waitFor(() => {
      expect(document.querySelector('.session-layout')).toHaveClass('desktop')
    })
    
    // Resize to mobile
    mockInnerWidth(600)
    
    await waitFor(() => {
      expect(document.querySelector('.session-layout')).toHaveClass('mobile')
    })
    
    // Resize back to desktop
    mockInnerWidth(1024)
    
    await waitFor(() => {
      expect(document.querySelector('.session-layout')).toHaveClass('desktop')
    })
  })
})