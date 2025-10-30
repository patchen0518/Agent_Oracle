// Basic App component test
// Based on React Testing Library best practices (Context 7 lookup: 2025-01-26)

import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import App from './App'

// Mock the API functions
vi.mock('./services/api', () => ({
  checkHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
  getSessions: vi.fn().mockResolvedValue([]),
  createSession: vi.fn(),
  updateSession: vi.fn(),
  deleteSession: vi.fn(),
  sendSessionMessage: vi.fn(),
  getSessionMessages: vi.fn().mockResolvedValue([])
}))

describe('App', () => {
  it('renders session layout with Oracle interface', async () => {
    render(<App />)
    
    // Should show Oracle branding in the empty state
    await waitFor(() => {
      expect(screen.getByText('This is Oracle')).toBeInTheDocument()
    })
  })

  it('shows backend status in session header', async () => {
    render(<App />)
    
    await waitFor(() => {
      expect(screen.getByText(/Backend:/)).toBeInTheDocument()
    })
  })

  it('shows empty state when no sessions exist', async () => {
    render(<App />)
    
    await waitFor(() => {
      expect(screen.getByText('Create or select a session to start chatting.')).toBeInTheDocument()
    })
  })
})