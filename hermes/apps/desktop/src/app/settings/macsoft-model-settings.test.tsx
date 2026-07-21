import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MacSoftModelSettings, shouldUseMacSoftModelSettings } from './macsoft-model-settings'

describe('MacSoftModelSettings', () => {
  const legacyApi = vi.fn()
  const loadModel = vi.fn(async () => ({ model: 'gpt-5.4', provider: 'openai-codex' }))
  const saveModel = vi.fn(async (settings: { model: string; provider: string }) => ({
    backups: ['runtime-config-backup'],
    changedFiles: ['runtime-config'],
    settings
  }))

  beforeEach(() => {
    Object.defineProperty(window, 'hermesDesktop', {
      configurable: true,
      value: {
        api: legacyApi,
        serverAutoCount: { loadModel, saveModel }
      }
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    delete (window as unknown as { hermesDesktop?: unknown }).hermesDesktop
  })

  it('loads the existing provider and model without calling the dashboard config API', async () => {
    render(<MacSoftModelSettings />)

    expect(await screen.findByDisplayValue('openai-codex')).toBeTruthy()
    expect(screen.getByDisplayValue('gpt-5.4')).toBeTruthy()
    expect(loadModel).toHaveBeenCalledTimes(1)
    expect(legacyApi).not.toHaveBeenCalled()
  })

  it('saves trimmed provider and model values through the product config bridge', async () => {
    render(<MacSoftModelSettings />)
    await screen.findByDisplayValue('openai-codex')

    fireEvent.change(screen.getByRole('textbox', { name: 'Provider' }), { target: { value: ' openrouter ' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Model' }), { target: { value: ' claude-sonnet-4 ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(saveModel).toHaveBeenCalledWith({ model: 'claude-sonnet-4', provider: 'openrouter' })
    )
    expect(await screen.findByText('Model settings saved.')).toBeTruthy()
    expect(legacyApi).not.toHaveBeenCalled()
  })

  it('shows a concise error without exposing bridge details', async () => {
    loadModel.mockRejectedValueOnce(new Error('C:\\ProgramData\\MacSoft Agent\\runtime\\config.yaml: EACCES'))
    render(<MacSoftModelSettings />)

    expect(await screen.findByText('Unable to load model settings.')).toBeTruthy()
    expect(document.body.textContent).not.toContain('ProgramData')
    expect(document.body.textContent).not.toContain('EACCES')
  })
})

describe('shouldUseMacSoftModelSettings', () => {
  it('selects the adapter only for packaged customer Model Settings', () => {
    expect(shouldUseMacSoftModelSettings(true, 'config:model')).toBe(true)
    expect(shouldUseMacSoftModelSettings(false, 'config:model')).toBe(false)
    expect(shouldUseMacSoftModelSettings(true, 'config:voice')).toBe(false)
  })
})
