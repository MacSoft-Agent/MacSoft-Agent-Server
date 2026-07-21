import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ServerAutoCountSettings } from '@/global'

import { ServerAutoCountSettingsPage } from './server-autocount-settings'

vi.mock('@/store/notifications', () => ({ notify: vi.fn() }))

const SETTINGS: ServerAutoCountSettings = {
  aiService: {
    port: 8642,
    status: { ok: true, summary: 'Internal service ready.', title: 'AI Service running' },
    url: 'http://127.0.0.1:8642'
  },
  autoCount: {
    apiKeyConfigured: true,
    cloudUrl: 'https://api.autocount.cloud',
    companyId: 'testing',
    connectorId: 'main-connector'
  },
  clientUrl: 'http://192.168.1.42:8787',
  localOnlyAddress: '127.0.0.1',
  networkAddresses: [
    {
      address: '192.168.1.42',
      id: 'Ethernet:192.168.1.42',
      interfaceName: 'Ethernet',
      kind: 'ethernet',
      recommended: true
    }
  ],
  projectRoot: 'C:\\MacSoft-Agent',
  recommendedAddress: '192.168.1.42',
  server: {
    port: 8787,
    status: { ok: true, summary: 'Client service ready.', title: 'MacSoft Server running' }
  },
  warnings: []
}

describe('ServerAutoCountSettingsPage', () => {
  const load = vi.fn(async () => SETTINGS)

  const refreshNetworks = vi.fn(async () => ({
    addresses: SETTINGS.networkAddresses,
    recommendedAddress: SETTINGS.recommendedAddress
  }))

  const save = vi.fn(async () => ({
    backups: [],
    changedFiles: [],
    restartRequired: false,
    servicesToRestart: [],
    settings: SETTINGS
  }))

  const testAiService = vi.fn(async () => SETTINGS.aiService.status)

  const testAutoCount = vi.fn(async () => ({
    fields: [
      { label: 'Connector', value: 'Online' },
      { label: 'Database', value: 'AED_Testing' }
    ],
    ok: true,
    summary: 'Cloud and connector ready.',
    title: 'AutoCount connected'
  }))

  const testServer = vi.fn(async () => SETTINGS.server.status)
  const getPairingCode = vi.fn(async () => 'PAIR-123456')
  const writeClipboard = vi.fn(async () => true)
  const hostStatus = vi.fn(async () => ({
    auto_start: true,
    product: 'MacSoft Agent' as const,
    version: '0.1.0',
    services: {
      ai_service: { last_error: null, name: 'ai_service' as const, owned: true, pid: 123, started_at: 1, status: 'running' as const },
      server: { last_error: null, name: 'server' as const, owned: true, pid: 456, started_at: 1, status: 'running' as const }
    }
  }))
  const serviceAction = vi.fn(async (name: 'ai_service' | 'server', action: 'restart' | 'start' | 'stop') => ({
    last_error: null,
    name,
    owned: action !== 'stop',
    pid: action === 'stop' ? null : 789,
    started_at: action === 'stop' ? null : 1,
    status: action === 'stop' ? 'stopped' as const : 'running' as const
  }))
  const setAutoStart = vi.fn(async (enabled: boolean) => enabled)

  beforeEach(() => {
    Object.defineProperty(window, 'hermesDesktop', {
      configurable: true,
      value: {
        macSoftHost: { serviceAction, setAutoStart, status: hostStatus },
        serverAutoCount: { getPairingCode, load, refreshNetworks, save, testAiService, testAutoCount, testServer },
        writeClipboard
      }
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    delete (window as unknown as { hermesDesktop?: unknown }).hermesDesktop
  })

  it('loads current values without exposing the existing API key', async () => {
    render(<ServerAutoCountSettingsPage />)

    expect(await screen.findByText('Server & AutoCount')).toBeTruthy()
    expect(screen.getByDisplayValue('http://192.168.1.42:8787')).toBeTruthy()
    expect((screen.getByPlaceholderText('Existing key configured · leave blank to keep') as HTMLInputElement).value).toBe('')
    expect(document.body.textContent).not.toContain('existing-secret')
  })

  it('regenerates and copies the Client URL from selected address and port', async () => {
    render(<ServerAutoCountSettingsPage />)
    await screen.findByText('Server & AutoCount')

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Server port' }), { target: { value: '8888' } })
    expect(screen.getByDisplayValue('http://192.168.1.42:8888')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Copy Client URL' }))

    await waitFor(() => expect(writeClipboard).toHaveBeenCalledWith('http://192.168.1.42:8888'))
  })

  it('formats AutoCount status instead of rendering raw JSON', async () => {
    render(<ServerAutoCountSettingsPage />)
    await screen.findByText('Server & AutoCount')
    fireEvent.click(screen.getByRole('button', { name: 'Test AutoCount Connection' }))

    expect(await screen.findByText('AutoCount connected')).toBeTruthy()
    expect(screen.getByText('AED_Testing')).toBeTruthy()
    expect(document.body.textContent).not.toContain('"ok":true')
  })

  it('routes service controls through the preload Host bridge', async () => {
    render(<ServerAutoCountSettingsPage />)
    await screen.findByText('Service Control')
    await waitFor(() => expect(hostStatus).toHaveBeenCalled())
    const restartButtons = screen.getAllByRole('button', { name: 'Restart' })
    fireEvent.click(restartButtons[0])
    await waitFor(() => expect(serviceAction).toHaveBeenCalledWith('ai_service', 'restart'))
  })

  it('gets and displays the pairing code through the Server settings bridge', async () => {
    render(<ServerAutoCountSettingsPage />)
    await screen.findByText('Pairing Code')

    fireEvent.click(screen.getByRole('button', { name: 'Get Code' }))

    await waitFor(() => expect(getPairingCode).toHaveBeenCalledWith(8787))
    expect(await screen.findByText('PAIR-123456')).toBeTruthy()
  })
})
