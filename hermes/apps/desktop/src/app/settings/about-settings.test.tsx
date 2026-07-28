import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  $desktopVersion,
  $updateChecking,
  $updateStatus
} from '@/store/updates'

import { AboutSettings } from './about-settings'

describe('AboutSettings MacSoft installer updates', () => {
  beforeEach(() => {
    $desktopVersion.set({
      appVersion: '0.1.0',
      buildId: 'macsoft-agent-0.1.0-stable.1',
      channel: 'stable',
      electronVersion: '40.0.0',
      nodeVersion: '24.0.0',
      platform: 'win32',
      updateMode: 'installer'
    })
    $updateChecking.set(false)
    $updateStatus.set(null)
  })

  afterEach(() => {
    cleanup()
  })

  it('shows installed version and checks through the existing About surface', () => {
    render(<AboutSettings />)

    expect(screen.getByText('Version 0.1.0')).toBeTruthy()
    expect(screen.getByText(/Build macsoft-agent-0.1.0-stable.1/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /check for updates/i })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /install update/i })).toBeNull()
  })

  it('offers an explicit install action only for a trusted available release', () => {
    $updateStatus.set({
      supported: true,
      updateAvailable: true,
      manifestConfigured: true,
      currentVersion: '0.1.0',
      currentBuildId: 'macsoft-agent-0.1.0-stable.1',
      targetVersion: '0.2.0',
      targetBuildId: 'macsoft-agent-0.2.0-stable.1',
      message: 'MacSoft Agent 0.2.0 is available.',
      fetchedAt: 1
    })

    render(<AboutSettings />)

    expect(screen.getByText('MacSoft Agent 0.2.0 is available')).toBeTruthy()
    expect(screen.getByText('Target build macsoft-agent-0.2.0-stable.1')).toBeTruthy()
    expect(screen.getByRole('button', { name: /install update/i })).toBeTruthy()
  })
})
