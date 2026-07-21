import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type {
  AutoCountTestInput,
  MacSoftHostStatus,
  MacSoftServiceAction,
  MacSoftServiceName,
  MacSoftServiceStatus,
  NetworkAddress,
  ReadableCheckResult,
  SaveServerAutoCountInput,
  ServerAutoCountSettings
} from '@/global'
import {
  AlertCircle,
  CheckCircle2,
  Copy,
  Cpu,
  Eye,
  EyeOff,
  Globe,
  KeyRound,
  Loader2,
  Play,
  RefreshCw,
  Save,
  Square
} from '@/lib/icons'
import { cn } from '@/lib/utils'
import { notify } from '@/store/notifications'

import { CONTROL_TEXT } from './constants'
import { ListRow, LoadingState, SectionHeading, SettingsContent } from './primitives'

interface FormState {
  aiServicePort: string
  aiServiceUrl: string
  apiKey: string
  apiKeyConfigured: boolean
  cloudUrl: string
  companyId: string
  connectorId: string
  serverPort: string
}

const EMPTY_FORM: FormState = {
  aiServicePort: '8642',
  aiServiceUrl: 'http://127.0.0.1:8642',
  apiKey: '',
  apiKeyConfigured: false,
  cloudUrl: '',
  companyId: '',
  connectorId: '',
  serverPort: '8787'
}

function formFromSettings(settings: ServerAutoCountSettings): FormState {
  return {
    aiServicePort: String(settings.aiService.port),
    aiServiceUrl: settings.aiService.url,
    apiKey: '',
    apiKeyConfigured: settings.autoCount.apiKeyConfigured,
    cloudUrl: settings.autoCount.cloudUrl,
    companyId: settings.autoCount.companyId,
    connectorId: settings.autoCount.connectorId,
    serverPort: String(settings.server.port)
  }
}

function withPort(rawUrl: string, rawPort: string): string {
  try {
    const url = new URL(rawUrl)
    url.port = rawPort

    return url.toString().replace(/\/$/, '')
  } catch {
    return rawUrl
  }
}

function StatusPanel({ result }: { result: ReadableCheckResult | null }) {
  if (!result) {
    return (
      <div className="rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3 text-xs text-(--ui-text-tertiary)">
        No connection test has been run yet.
      </div>
    )
  }

  return (
    <div
      className={cn(
        'rounded-xl border px-4 py-3',
        result.ok
          ? 'border-emerald-500/25 bg-emerald-500/5'
          : 'border-destructive/30 bg-destructive/5'
      )}
    >
      <div className="flex items-start gap-2">
        {result.ok ? (
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
        ) : (
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
        )}
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">{result.title}</p>
          <p className="mt-1 text-xs leading-5 text-(--ui-text-tertiary)">{result.summary}</p>
          {result.action ? <p className="mt-2 text-xs leading-5 text-foreground">Next: {result.action}</p> : null}
        </div>
      </div>

      {result.fields?.length ? (
        <dl className="mt-3 grid gap-x-5 gap-y-2 border-t border-(--ui-stroke-tertiary) pt-3 text-xs sm:grid-cols-2">
          {result.fields.map(field => (
            <div className="min-w-0" key={field.label}>
              <dt className="text-(--ui-text-tertiary)">{field.label}</dt>
              <dd className="mt-0.5 break-words font-medium text-foreground">{field.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {result.details ? (
        <details className="mt-3 border-t border-(--ui-stroke-tertiary) pt-2 text-xs text-(--ui-text-tertiary)">
          <summary className="cursor-pointer select-none">Administrator detail</summary>
          <p className="mt-2 font-mono">{result.details}</p>
        </details>
      ) : null}
    </div>
  )
}

function networkLabel(network: NetworkAddress): string {
  const kind = {
    ethernet: 'Ethernet',
    other: 'Network',
    vpn: 'VPN',
    virtual: 'Virtual',
    wifi: 'Wi-Fi'
  }[network.kind]

  return `${network.interfaceName} · ${kind} · ${network.address}${network.recommended ? ' · Recommended' : ''}`
}

function ServiceControl({
  busy,
  label,
  onAction,
  service
}: {
  busy: boolean
  label: string
  onAction: (action: MacSoftServiceAction) => void
  service: MacSoftServiceStatus | undefined
}) {
  const status = service?.status || 'stopped'
  const tone = status === 'running' ? 'text-emerald-600 dark:text-emerald-400' : status === 'error' ? 'text-destructive' : 'text-(--ui-text-tertiary)'
  return (
    <div className="rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className={cn('mt-1 text-xs capitalize', tone)}>{status.replace('_', ' ')}</p>
          {service?.last_error ? <p className="mt-1 max-w-xl text-xs text-destructive">{service.last_error}</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy || status === 'running' || status === 'starting'} onClick={() => onAction('start')} size="sm" variant="outline">
            <Play /> Start
          </Button>
          <Button disabled={busy || status === 'stopped'} onClick={() => onAction('stop')} size="sm" variant="outline">
            <Square /> Stop
          </Button>
          <Button disabled={busy || status === 'stopped'} onClick={() => onAction('restart')} size="sm" variant="outline">
            <RefreshCw /> Restart
          </Button>
        </div>
      </div>
    </div>
  )
}

export function ServerAutoCountSettingsPage() {
  const api = window.hermesDesktop?.serverAutoCount
  const hostApi = window.hermesDesktop?.macSoftHost
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState<'ai' | 'autocount' | 'server' | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)
  const [settings, setSettings] = useState<ServerAutoCountSettings | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [selectedAddress, setSelectedAddress] = useState('')
  const [serverStatus, setServerStatus] = useState<ReadableCheckResult | null>(null)
  const [aiStatus, setAiStatus] = useState<ReadableCheckResult | null>(null)
  const [autoCountStatus, setAutoCountStatus] = useState<ReadableCheckResult | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [hostStatus, setHostStatus] = useState<MacSoftHostStatus | null>(null)
  const [hostError, setHostError] = useState<string | null>(null)
  const [serviceAction, setServiceAction] = useState<MacSoftServiceName | null>(null)
  const [pairingCode, setPairingCode] = useState<string | null>(null)
  const [pairingError, setPairingError] = useState<string | null>(null)
  const [gettingPairingCode, setGettingPairingCode] = useState(false)

  const applyLoadedSettings = (next: ServerAutoCountSettings) => {
    setSettings(next)
    setForm(formFromSettings(next))
    setServerStatus(next.server.status)
    setAiStatus(next.aiService.status)
    setSelectedAddress(current => {
      if (next.networkAddresses.some(network => network.address === current) || current === next.localOnlyAddress) {
        return current
      }

      return next.recommendedAddress || next.localOnlyAddress
    })
  }

  const load = async () => {
    if (!api) {
      setLoadError('The Desktop configuration bridge is unavailable.')
      setLoading(false)

      return
    }

    setLoading(true)
    setLoadError(null)

    try {
      applyLoadedSettings(await api.load())
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Could not load Server & AutoCount settings.')
    } finally {
      setLoading(false)
    }
  }

  const refreshHostStatus = async () => {
    if (!hostApi) {
      setHostError('The Desktop Host bridge is unavailable.')
      return
    }
    try {
      setHostStatus(await hostApi.status())
      setHostError(null)
    } catch (error) {
      setHostError(error instanceof Error ? error.message : 'MacSoft Agent Host is unavailable.')
    }
  }

  const runServiceAction = async (name: MacSoftServiceName, action: MacSoftServiceAction) => {
    if (!hostApi) return
    setServiceAction(name)
    try {
      await hostApi.serviceAction(name, action)
      await refreshHostStatus()
    } catch (error) {
      setHostError(error instanceof Error ? error.message : 'The service action failed.')
    } finally {
      setServiceAction(null)
    }
  }

  const setAutoStart = async (enabled: boolean) => {
    if (!hostApi) return
    try {
      const autoStart = await hostApi.setAutoStart(enabled)
      setHostStatus(current => (current ? { ...current, auto_start: autoStart } : current))
    } catch (error) {
      setHostError(error instanceof Error ? error.message : 'Auto-start could not be updated.')
    }
  }

  useEffect(() => {
    void load()
    void refreshHostStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once when the page opens
  }, [])

  const clientUrl = useMemo(
    () => `http://${selectedAddress || settings?.recommendedAddress || settings?.localOnlyAddress || '127.0.0.1'}:${form.serverPort || '8787'}`,
    [form.serverPort, selectedAddress, settings?.localOnlyAddress, settings?.recommendedAddress]
  )

  const savePayload = (): SaveServerAutoCountInput => ({
    aiServicePort: Number(form.aiServicePort),
    aiServiceUrl: form.aiServiceUrl,
    apiKey: form.apiKey.trim() || undefined,
    cloudUrl: form.cloudUrl,
    companyId: form.companyId,
    connectorId: form.connectorId,
    serverPort: Number(form.serverPort)
  })

  const autoCountPayload = (): AutoCountTestInput => ({
    apiKey: form.apiKey.trim() || undefined,
    cloudUrl: form.cloudUrl,
    companyId: form.companyId,
    connectorId: form.connectorId
  })

  const refreshNetworks = async () => {
    if (!api) {
      return
    }

    try {
      const network = await api.refreshNetworks()
      setSettings(current =>
        current
          ? { ...current, networkAddresses: network.addresses, recommendedAddress: network.recommendedAddress }
          : current
      )
      setSelectedAddress(network.recommendedAddress || '127.0.0.1')
    } catch (error) {
      notify({
        kind: 'error',
        message: error instanceof Error ? error.message : 'Network interfaces could not be refreshed.',
        title: 'Refresh failed'
      })
    }
  }

  const copyClientUrl = async () => {
    try {
      await window.hermesDesktop.writeClipboard(clientUrl)
      notify({ kind: 'success', message: clientUrl, title: 'Client URL copied' })
    } catch {
      notify({ kind: 'error', message: 'Copy the URL manually from the field.', title: 'Copy failed' })
    }
  }

  const getPairingCode = async () => {
    if (!api) return

    setGettingPairingCode(true)
    setPairingCode(null)
    setPairingError(null)

    try {
      setPairingCode(await api.getPairingCode(Number(form.serverPort)))
    } catch {
      setPairingError('Unable to get pairing code.')
    } finally {
      setGettingPairingCode(false)
    }
  }

  const testServer = async () => {
    if (!api) {
      return
    }

    setTesting('server')

    try {
      setServerStatus(await api.testServer(Number(form.serverPort)))
    } finally {
      setTesting(null)
    }
  }

  const testAiService = async () => {
    if (!api) {
      return
    }

    setTesting('ai')

    try {
      setAiStatus(await api.testAiService(withPort(form.aiServiceUrl, form.aiServicePort)))
    } finally {
      setTesting(null)
    }
  }

  const testAutoCount = async () => {
    if (!api) {
      return
    }

    setTesting('autocount')

    try {
      setAutoCountStatus(await api.testAutoCount(autoCountPayload()))
    } catch (error) {
      setAutoCountStatus({
        action: 'Review the fields and try again.',
        ok: false,
        summary: error instanceof Error ? error.message : 'The connection test could not be completed.',
        title: 'AutoCount test failed'
      })
    } finally {
      setTesting(null)
    }
  }

  const save = async () => {
    if (!api) {
      return
    }

    setSaving(true)

    try {
      const result = await api.save(savePayload())
      applyLoadedSettings(result.settings)
      setAutoCountStatus(null)
      notify({
        kind: 'success',
        message: result.restartRequired
          ? `Saved safely. Restart required: ${result.servicesToRestart.join(', ')}.`
          : 'Saved safely. No service restart is required.',
        title: 'Server & AutoCount settings saved'
      })
    } catch (error) {
      notify({
        kind: 'error',
        message: error instanceof Error ? error.message : 'The settings could not be saved.',
        title: 'Save failed'
      })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <LoadingState label="Loading Server & AutoCount settings..." />
  }

  if (loadError || !settings) {
    return (
      <SettingsContent>
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3">
          <p className="text-sm font-medium text-destructive">Settings could not be loaded</p>
          <p className="mt-1 text-xs leading-5 text-(--ui-text-tertiary)">{loadError}</p>
          <Button className="mt-3" onClick={() => void load()} size="sm" variant="outline">
            <RefreshCw /> Retry
          </Button>
        </div>
      </SettingsContent>
    )
  }

  return (
    <SettingsContent>
      <div className="mb-6">
        <h2 className="text-lg font-semibold tracking-tight">Server & AutoCount</h2>
        <p className="mt-1 max-w-2xl text-xs leading-5 text-(--ui-text-tertiary)">
          Configure the Client-facing MacSoft Server, internal AI Service, and AutoCount Cloud connection. Saving never starts or stops a service automatically.
        </p>
      </div>

      <SectionHeading icon={Cpu} title="Service Control" />
      <div className="grid gap-3">
        <ServiceControl
          busy={serviceAction === 'ai_service'}
          label="AI Service"
          onAction={action => void runServiceAction('ai_service', action)}
          service={hostStatus?.services.ai_service}
        />
        <ServiceControl
          busy={serviceAction === 'server'}
          label="MacSoft Server"
          onAction={action => void runServiceAction('server', action)}
          service={hostStatus?.services.server}
        />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <Button onClick={() => void refreshHostStatus()} size="sm" variant="textStrong">
          <RefreshCw /> Refresh Status
        </Button>
        <label className="flex items-center gap-2 text-xs text-foreground">
          <input
            checked={hostStatus?.auto_start ?? true}
            disabled={!hostStatus}
            onChange={event => void setAutoStart(event.target.checked)}
            type="checkbox"
          />
          Auto-start services with Windows
        </label>
      </div>
      {hostError ? <p className="mt-3 text-xs text-destructive">{hostError}</p> : null}
      <details className="mt-3 rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3 text-xs text-(--ui-text-tertiary)">
        <summary className="cursor-pointer select-none">Administrator details</summary>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2">
          <div><dt>Host version</dt><dd className="font-mono text-foreground">{hostStatus?.version || 'Unavailable'}</dd></div>
          <div><dt>AI Service PID</dt><dd className="font-mono text-foreground">{hostStatus?.services.ai_service.pid || 'Not running'}</dd></div>
          <div><dt>Server PID</dt><dd className="font-mono text-foreground">{hostStatus?.services.server.pid || 'Not running'}</dd></div>
          <div><dt>Control boundary</dt><dd className="text-foreground">Local Host interface only</dd></div>
        </dl>
      </details>

      {settings.warnings.map(warning => (
        <div
          className="mb-4 flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2.5 text-xs"
          key={warning}
        >
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <span>{warning}</span>
        </div>
      ))}

      <SectionHeading icon={Globe} title="MacSoft Server" />
      <div className="grid gap-1">
        <ListRow
          action={
            <Input
              aria-label="Server port"
              className={cn('h-8 w-36', CONTROL_TEXT)}
              max={65535}
              min={1}
              onChange={event => setForm(current => ({ ...current, serverPort: event.target.value }))}
              type="number"
              value={form.serverPort}
            />
          }
          description="Client-facing port. MacSoft Client connects here, not to the AI Service."
          title="Server port"
        />
        <ListRow
          action={
            <select
              aria-label="Selected network interface"
              className="h-8 min-w-64 max-w-full rounded-md border border-input bg-transparent px-2 text-xs text-foreground"
              onChange={event => setSelectedAddress(event.target.value)}
              value={selectedAddress}
            >
              {settings.networkAddresses.map(network => (
                <option key={network.id} value={network.address}>
                  {networkLabel(network)}
                </option>
              ))}
              <option value={settings.localOnlyAddress}>This computer only · 127.0.0.1</option>
            </select>
          }
          description="Physical Wi-Fi or Ethernet is recommended. Virtual and VPN addresses remain selectable."
          title="Network interface"
        />
        <ListRow
          action={
            <div className="flex max-w-full items-center gap-2">
              <Input aria-label="Client URL" className="h-8 min-w-0 font-mono text-xs" readOnly value={clientUrl} />
              <Button aria-label="Copy Client URL" onClick={() => void copyClientUrl()} size="icon-sm" variant="outline">
                <Copy />
              </Button>
            </div>
          }
          description={
            selectedAddress === settings.localOnlyAddress
              ? 'Local-only URL. Other computers cannot use this address.'
              : 'Share this URL with MacSoft Client devices on the same local network.'
          }
          title="Client URL"
        />
        <ListRow
          action={
            <div className="flex items-center gap-3">
              <Button
                disabled={hostStatus?.services.server.status !== 'running' || gettingPairingCode}
                onClick={() => void getPairingCode()}
                size="sm"
                variant="outline"
              >
                {gettingPairingCode ? <Loader2 className="animate-spin" /> : null}
                Get Code
              </Button>
              {pairingCode ? <span className="font-mono text-sm font-semibold text-foreground">{pairingCode}</span> : null}
            </div>
          }
          description={
            hostStatus?.services.server.status !== 'running'
              ? 'MacSoft Server is not running.'
              : pairingError || 'Request a one-time code for pairing a MacSoft Client.'
          }
          title="Pairing Code"
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-4">
        <Button onClick={() => void refreshNetworks()} size="sm" variant="textStrong">
          <RefreshCw /> Refresh IP
        </Button>
        <Button disabled={testing === 'server'} onClick={() => void testServer()} size="sm" variant="outline">
          {testing === 'server' ? <Loader2 className="animate-spin" /> : null}
          Test Server
        </Button>
      </div>
      <div className="mt-4">
        <StatusPanel result={serverStatus} />
      </div>

      <details className="mt-8 rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3">
        <summary className="cursor-pointer select-none text-sm font-medium">Advanced · AI Service</summary>
        <div className="mt-4">
          <SectionHeading icon={Cpu} title="AI Service" />
          <div className="grid gap-1">
            <ListRow
              action={
                <Input
                  aria-label="AI Service URL"
                  className={cn('h-8 font-mono', CONTROL_TEXT)}
                  onChange={event => setForm(current => ({ ...current, aiServiceUrl: event.target.value }))}
                  value={form.aiServiceUrl}
                />
              }
              description="Internal service used by MacSoft Server. It is not a Client URL."
              title="Service URL"
            />
            <ListRow
              action={
                <Input
                  aria-label="AI Service port"
                  className={cn('h-8 w-36', CONTROL_TEXT)}
                  max={65535}
                  min={1}
                  onChange={event => setForm(current => ({ ...current, aiServicePort: event.target.value }))}
                  type="number"
                  value={form.aiServicePort}
                />
              }
              description="Changing this updates the runtime API Server port and MacSoft Server URL together."
              title="Service port"
            />
          </div>
          <Button
            className="mt-3"
            disabled={testing === 'ai'}
            onClick={() => void testAiService()}
            size="sm"
            variant="outline"
          >
            {testing === 'ai' ? <Loader2 className="animate-spin" /> : null}
            Test AI Service
          </Button>
          <div className="mt-4">
            <StatusPanel result={aiStatus} />
          </div>
        </div>
      </details>

      <div className="mt-8">
        <SectionHeading icon={KeyRound} title="AutoCount Connection" />
        <div className="grid gap-1">
          <ListRow
            action={
              <Input
                className={cn('h-8 font-mono', CONTROL_TEXT)}
                onChange={event => setForm(current => ({ ...current, cloudUrl: event.target.value }))}
                value={form.cloudUrl}
              />
            }
            description="AutoCount Cloud API base URL."
            title="Cloud URL"
          />
          <ListRow
            action={
              <div className="flex items-center gap-2">
                <Input
                  autoComplete="off"
                  className={cn('h-8 font-mono', CONTROL_TEXT)}
                  onChange={event => setForm(current => ({ ...current, apiKey: event.target.value }))}
                  placeholder={form.apiKeyConfigured ? 'Existing key configured · leave blank to keep' : 'Enter API Key'}
                  type={showApiKey ? 'text' : 'password'}
                  value={form.apiKey}
                />
                <Button
                  aria-label={showApiKey ? 'Hide API Key' : 'Reveal typed API Key'}
                  onClick={() => setShowApiKey(value => !value)}
                  size="icon-sm"
                  type="button"
                  variant="outline"
                >
                  {showApiKey ? <EyeOff /> : <Eye />}
                </Button>
              </div>
            }
            description="The existing key is never loaded into this page. Leave blank to preserve it; do not include a Bearer prefix."
            title="API Key"
          />
          <ListRow
            action={
              <Input
                className={cn('h-8 font-mono', CONTROL_TEXT)}
                onChange={event => setForm(current => ({ ...current, connectorId: event.target.value }))}
                value={form.connectorId}
              />
            }
            description="Selects the registered Local Connector."
            title="Connector ID"
          />
          <ListRow
            action={
              <Input
                className={cn('h-8 font-mono', CONTROL_TEXT)}
                onChange={event => setForm(current => ({ ...current, companyId: event.target.value }))}
                value={form.companyId}
              />
            }
            description="Selects the company/account book exposed by the Connector. Database details are read-only test results."
            title="Company ID"
          />
        </div>

        <Button
          className="mt-3"
          disabled={testing === 'autocount'}
          onClick={() => void testAutoCount()}
          size="sm"
          variant="outline"
        >
          {testing === 'autocount' ? <Loader2 className="animate-spin" /> : null}
          Test AutoCount Connection
        </Button>
        <div className="mt-4">
          <StatusPanel result={autoCountStatus} />
        </div>
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-end gap-3 border-t border-(--ui-stroke-tertiary) pt-5">
        <p className="mr-auto max-w-xl text-xs leading-5 text-(--ui-text-tertiary)">
          Save creates timestamped backups and atomically replaces validated configuration files. The result will list any required service restarts.
        </p>
        <Button disabled={saving} onClick={() => void save()} size="sm">
          {saving ? <Loader2 className="animate-spin" /> : <Save />}
          Save & Apply
        </Button>
      </div>
    </SettingsContent>
  )
}
