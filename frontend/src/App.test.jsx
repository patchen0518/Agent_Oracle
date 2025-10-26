// Basic App component test
// Based on React Testing Library best practices (Context 7 lookup: 2025-01-26)

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders Oracle Chat title', () => {
    render(<App />)
    expect(screen.getByText('Oracle Chat')).toBeInTheDocument()
  })

  it('shows backend status', () => {
    render(<App />)
    expect(screen.getByText(/Backend:/)).toBeInTheDocument()
  })
})