import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { MacSoftModelSettings as MacSoftModelSettingsValue } from '@/global'
import { Cpu, Loader2, Save } from '@/lib/icons'

import { CONTROL_TEXT } from './constants'
import { ListRow, LoadingState, SectionHeading, SettingsContent } from './primitives'

const EMPTY_SETTINGS: MacSoftModelSettingsValue = { model: '', provider: '' }

export function shouldUseMacSoftModelSettings(customerRuntime: boolean, activeView: string): boolean {
  return customerRuntime && activeView === 'config:model'
}

export function MacSoftModelSettings() {
  const api = window.hermesDesktop?.serverAutoCount
  const [settings, setSettings] = useState<MacSoftModelSettingsValue>(EMPTY_SETTINGS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      if (!api?.loadModel) {
        if (!cancelled) {
          setError('Unable to load model settings.')
          setLoading(false)
        }

        return
      }

      try {
        const loaded = await api.loadModel()

        if (!cancelled) {
          setSettings(loaded)
          setError(null)
        }
      } catch {
        if (!cancelled) {
          setError('Unable to load model settings.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()

    return () => void (cancelled = true)
  }, [api])

  const save = async () => {
    if (!api?.saveModel || !settings.provider.trim() || !settings.model.trim()) {
      setMessage(null)
      setError('Provider and model are required.')

      return
    }

    setSaving(true)
    setMessage(null)
    setError(null)

    try {
      const result = await api.saveModel({
        model: settings.model.trim(),
        provider: settings.provider.trim()
      })
      setSettings(result.settings)
      setMessage('Model settings saved.')
    } catch {
      setError('Unable to save model settings.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <LoadingState label="Loading model settings" />
  }

  return (
    <SettingsContent>
      <SectionHeading icon={Cpu} title="Model Settings" />
      <p className="mb-4 text-xs leading-5 text-(--ui-text-tertiary)">
        Configure the provider and model used by MacSoft Agent for new requests.
      </p>

      <div className="grid gap-1">
        <ListRow
          action={
            <Input
              aria-label="Provider"
              autoComplete="off"
              className={CONTROL_TEXT}
              disabled={saving}
              onChange={event => setSettings(current => ({ ...current, provider: event.target.value }))}
              spellCheck={false}
              value={settings.provider}
            />
          }
          description="Provider identifier configured for the internal AI Service."
          title="Provider"
        />
        <ListRow
          action={
            <Input
              aria-label="Model"
              autoComplete="off"
              className={CONTROL_TEXT}
              disabled={saving}
              onChange={event => setSettings(current => ({ ...current, model: event.target.value }))}
              spellCheck={false}
              value={settings.model}
            />
          }
          description="Model identifier used for new chat requests."
          title="Model"
        />
      </div>

      {error ? (
        <p className="mt-3 text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="mt-3 text-xs text-emerald-600 dark:text-emerald-400" role="status">
          {message}
        </p>
      ) : null}

      <div className="mt-5 flex justify-end">
        <Button disabled={saving} onClick={() => void save()}>
          {saving ? <Loader2 className="animate-spin" /> : <Save />}
          Save
        </Button>
      </div>
    </SettingsContent>
  )
}
