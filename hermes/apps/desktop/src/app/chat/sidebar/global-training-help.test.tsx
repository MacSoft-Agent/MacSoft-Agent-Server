import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { GlobalTrainingHelp } from './global-training-help'

const STORAGE_KEY = 'macsoft.global-training-help-seen.v1'

beforeAll(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      disconnect() {}
      observe() {}
      unobserve() {}
    }
  )
})

afterAll(() => vi.unstubAllGlobals())

afterEach(() => {
  cleanup()
  window.localStorage.clear()
})

describe('GlobalTrainingHelp', () => {
  it('explains impact, proposal approval, modes, and privacy from the question button', () => {
    render(<GlobalTrainingHelp entrySignal={0} />)

    fireEvent.click(screen.getByRole('button', { name: 'About Global Training' }))

    expect(screen.getByText('What is Global Training?')).toBeTruthy()
    expect(screen.getByText(/inherited by every Client/i)).toBeTruthy()
    expect(screen.getByText(/Proposal/i)).toBeTruthy()
    expect(screen.getAllByText(/General/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Targeted/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/personal or customer-private information/i)).toBeTruthy()
  })

  it('opens once on first entry and persists acknowledgement', () => {
    const rendered = render(<GlobalTrainingHelp entrySignal={0} />)

    rendered.rerender(<GlobalTrainingHelp entrySignal={1} />)
    expect(screen.getByText('What is Global Training?')).toBeTruthy()
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('1')

    rendered.unmount()
    const revisited = render(<GlobalTrainingHelp entrySignal={0} />)
    revisited.rerender(<GlobalTrainingHelp entrySignal={1} />)
    expect(screen.queryByText('What is Global Training?')).toBeNull()
  })
})
