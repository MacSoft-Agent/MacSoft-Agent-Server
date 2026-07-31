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
import { useI18n } from '@/i18n'
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

export function macSoftSettingsErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error) || !error.message.trim()) {
    return fallback
  }

  return (
    error.message
      .replace(/^Error invoking remote method '[^']+':\s*/i, '')
      .replace(/^Error:\s*/i, '')
      .trim() || fallback
  )
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
  const c = useI18n().t.settings.serverAutoCount

  if (!result) {
    return (
      <div className="rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3 text-xs text-(--ui-text-tertiary)">
        {c.noTestRun}
      </div>
    )
  }

  return (
    <div
      className={cn(
        'rounded-xl border px-4 py-3',
        result.ok ? 'border-emerald-500/25 bg-emerald-500/5' : 'border-destructive/30 bg-destructive/5'
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
          {result.action ? (
            <p className="mt-2 text-xs leading-5 text-foreground">
              {c.next}: {result.action}
            </p>
          ) : null}
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
          <summary className="cursor-pointer select-none">{c.administratorDetail}</summary>
          <p className="mt-2 font-mono">{result.details}</p>
        </details>
      ) : null}
    </div>
  )
}

function networkLabel(network: NetworkAddress, kind: string, recommended: string): string {
  return `${network.interfaceName} · ${kind} · ${network.address}${network.recommended ? ` · ${recommended}` : ''}`
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
  const c = useI18n().t.settings.serverAutoCount
  const status = service?.status || 'stopped'

  const tone =
    status === 'running'
      ? 'text-emerald-600 dark:text-emerald-400'
      : status === 'error'
        ? 'text-destructive'
        : 'text-(--ui-text-tertiary)'

  return (
    <div className="rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className={cn('mt-1 text-xs capitalize', tone)}>{c.serviceStatuses[status]}</p>
          {service?.last_error ? <p className="mt-1 max-w-xl text-xs text-destructive">{service.last_error}</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={busy || status === 'running' || status === 'starting'}
            onClick={() => onAction('start')}
            size="sm"
            variant="outline"
          >
            <Play /> {c.start}
          </Button>
          <Button disabled={busy || status === 'stopped'} onClick={() => onAction('stop')} size="sm" variant="outline">
            <Square /> {c.stop}
          </Button>
          <Button
            disabled={busy || status === 'stopped'}
            onClick={() => onAction('restart')}
            size="sm"
            variant="outline"
          >
            <RefreshCw /> {c.restart}
          </Button>
        </div>
      </div>
    </div>
  )
}

export function ServerAutoCountSettingsPage() {
  const c = useI18n().t.settings.serverAutoCount
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
      setLoadError(c.desktopBridgeUnavailable)
      setLoading(false)

      return
    }

    setLoading(true)
    setLoadError(null)

    try {
      applyLoadedSettings(await api.load())
    } catch (error) {
      setLoadError(macSoftSettingsErrorMessage(error, c.settingsLoadFailed))
    } finally {
      setLoading(false)
    }
  }

  const refreshHostStatus = async () => {
    if (!hostApi) {
      setHostError(c.hostBridgeUnavailable)

      return
    }

    try {
      setHostStatus(await hostApi.status())
      setHostError(null)
    } catch (error) {
      setHostError(macSoftSettingsErrorMessage(error, c.hostUnavailable))
    }
  }

  const runServiceAction = async (name: MacSoftServiceName, action: MacSoftServiceAction) => {
    if (!hostApi) {
      return
    }

    setServiceAction(name)

    try {
      await hostApi.serviceAction(name, action)
      await refreshHostStatus()
    } catch (error) {
      setHostError(macSoftSettingsErrorMessage(error, c.serviceActionFailed))
    } finally {
      setServiceAction(null)
    }
  }

  const setAutoStart = async (enabled: boolean) => {
    if (!hostApi) {
      return
    }

    try {
      const autoStart = await hostApi.setAutoStart(enabled)
      setHostStatus(current => (current ? { ...current, auto_start: autoStart } : current))
    } catch (error) {
      setHostError(macSoftSettingsErrorMessage(error, c.autoStartUpdateFailed))
    }
  }

  useEffect(() => {
    void load()
    void refreshHostStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once when the page opens
  }, [])

  const clientUrl = useMemo(
    () =>
      `http://${selectedAddress || settings?.recommendedAddress || settings?.localOnlyAddress || '127.0.0.1'}:${form.serverPort || '8787'}`,
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
        message: macSoftSettingsErrorMessage(error, c.networkRefreshFailed),
        title: c.refreshFailed
      })
    }
  }

  const copyClientUrl = async () => {
    try {
      await window.hermesDesktop.writeClipboard(clientUrl)
      notify({ kind: 'success', message: clientUrl, title: c.clientUrlCopied })
    } catch {
      notify({ kind: 'error', message: c.copyManually, title: c.copyFailed })
    }
  }

  const getPairingCode = async () => {
    if (!api) {
      return
    }

    setGettingPairingCode(true)
    setPairingCode(null)
    setPairingError(null)

    try {
      setPairingCode(await api.getPairingCode(Number(form.serverPort)))
    } catch {
      setPairingError(c.pairingCodeFailed)
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
        action: c.reviewFields,
        ok: false,
        summary: macSoftSettingsErrorMessage(error, c.connectionTestFailed),
        title: c.autoCountTestFailed
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
          ? c.savedRestartRequired(result.servicesToRestart.join(', '))
          : c.savedNoRestart,
        title: c.settingsSaved
      })
    } catch (error) {
      notify({
        kind: 'error',
        message: macSoftSettingsErrorMessage(error, c.settingsSaveFailed),
        title: c.saveFailed
      })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <LoadingState label={c.loading} />
  }

  if (loadError || !settings) {
    return (
      <SettingsContent>
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3">
          <p className="text-sm font-medium text-destructive">{c.loadPageFailed}</p>
          <p className="mt-1 text-xs leading-5 text-(--ui-text-tertiary)">{loadError}</p>
          <Button className="mt-3" onClick={() => void load()} size="sm" variant="outline">
            <RefreshCw /> {c.retry}
          </Button>
        </div>
      </SettingsContent>
    )
  }

  return (
    <SettingsContent>
      <div className="mb-6">
        <h2 className="text-lg font-semibold tracking-tight">{c.title}</h2>
        <p className="mt-1 max-w-2xl text-xs leading-5 text-(--ui-text-tertiary)">{c.intro}</p>
      </div>

      <SectionHeading icon={Cpu} title={c.serviceControl} />
      <div className="grid gap-3">
        <ServiceControl
          busy={serviceAction === 'ai_service'}
          label={c.aiService}
          onAction={action => void runServiceAction('ai_service', action)}
          service={hostStatus?.services.ai_service}
        />
        <ServiceControl
          busy={serviceAction === 'server'}
          label={c.macsoftServer}
          onAction={action => void runServiceAction('server', action)}
          service={hostStatus?.services.server}
        />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <Button onClick={() => void refreshHostStatus()} size="sm" variant="textStrong">
          <RefreshCw /> {c.refreshStatus}
        </Button>
        <label className="flex items-center gap-2 text-xs text-foreground">
          <input
            checked={hostStatus?.auto_start ?? true}
            disabled={!hostStatus}
            onChange={event => void setAutoStart(event.target.checked)}
            type="checkbox"
          />
          {c.autoStartWithWindows}
        </label>
      </div>
      {hostError ? <p className="mt-3 text-xs text-destructive">{hostError}</p> : null}
      <details className="mt-3 rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3 text-xs text-(--ui-text-tertiary)">
        <summary className="cursor-pointer select-none">{c.administratorDetails}</summary>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2">
          <div>
            <dt>{c.hostVersion}</dt>
            <dd className="font-mono text-foreground">{hostStatus?.version || c.unavailable}</dd>
          </div>
          <div>
            <dt>{c.aiServicePid}</dt>
            <dd className="font-mono text-foreground">{hostStatus?.services.ai_service.pid || c.notRunning}</dd>
          </div>
          <div>
            <dt>{c.serverPid}</dt>
            <dd className="font-mono text-foreground">{hostStatus?.services.server.pid || c.notRunning}</dd>
          </div>
          <div>
            <dt>{c.controlBoundary}</dt>
            <dd className="text-foreground">{c.localHostOnly}</dd>
          </div>
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

      <SectionHeading icon={Globe} title={c.macsoftServer} />
      <div className="grid gap-1">
        <ListRow
          action={
            <Input
              aria-label={c.serverPort}
              className={cn('h-8 w-36', CONTROL_TEXT)}
              max={65535}
              min={1}
              onChange={event => setForm(current => ({ ...current, serverPort: event.target.value }))}
              type="number"
              value={form.serverPort}
            />
          }
          description={c.serverPortDesc}
          title={c.serverPort}
        />
        <ListRow
          action={
            <select
              aria-label={c.networkInterfaceAria}
              className="h-8 min-w-64 max-w-full rounded-md border border-input bg-transparent px-2 text-xs text-foreground"
              onChange={event => setSelectedAddress(event.target.value)}
              value={selectedAddress}
            >
              {settings.networkAddresses.map(network => (
                <option key={network.id} value={network.address}>
                  {networkLabel(network, c.networkKinds[network.kind] ?? network.kind, c.recommended)}
                </option>
              ))}
              <option value={settings.localOnlyAddress}>{c.thisComputerOnly} · 127.0.0.1</option>
            </select>
          }
          description={c.networkInterfaceDesc}
          title={c.networkInterface}
        />
        <ListRow
          action={
            <div className="flex max-w-full items-center gap-2">
              <Input aria-label={c.clientUrl} className="h-8 min-w-0 font-mono text-xs" readOnly value={clientUrl} />
              <Button
                aria-label={c.copyClientUrl}
                onClick={() => void copyClientUrl()}
                size="icon-sm"
                variant="outline"
              >
                <Copy />
              </Button>
            </div>
          }
          description={selectedAddress === settings.localOnlyAddress ? c.clientUrlLocalDesc : c.clientUrlDesc}
          title={c.clientUrl}
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
                {c.getCode}
              </Button>
              {pairingCode ? (
                <span className="font-mono text-sm font-semibold text-foreground">{pairingCode}</span>
              ) : null}
            </div>
          }
          description={
            hostStatus?.services.server.status !== 'running' ? c.serverNotRunning : pairingError || c.pairingCodeDesc
          }
          title={c.pairingCode}
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-4">
        <Button onClick={() => void refreshNetworks()} size="sm" variant="textStrong">
          <RefreshCw /> {c.refreshIp}
        </Button>
        <Button disabled={testing === 'server'} onClick={() => void testServer()} size="sm" variant="outline">
          {testing === 'server' ? <Loader2 className="animate-spin" /> : null}
          {c.testServer}
        </Button>
      </div>
      <div className="mt-4">
        <StatusPanel result={serverStatus} />
      </div>

      <details className="mt-8 rounded-xl border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-4 py-3">
        <summary className="cursor-pointer select-none text-sm font-medium">{c.advancedAiService}</summary>
        <div className="mt-4">
          <SectionHeading icon={Cpu} title={c.aiService} />
          <div className="grid gap-1">
            <ListRow
              action={
                <Input
                  aria-label={c.serviceUrl}
                  className={cn('h-8 font-mono', CONTROL_TEXT)}
                  onChange={event => setForm(current => ({ ...current, aiServiceUrl: event.target.value }))}
                  value={form.aiServiceUrl}
                />
              }
              description={c.serviceUrlDesc}
              title={c.serviceUrl}
            />
            <ListRow
              action={
                <Input
                  aria-label={c.servicePort}
                  className={cn('h-8 w-36', CONTROL_TEXT)}
                  max={65535}
                  min={1}
                  onChange={event => setForm(current => ({ ...current, aiServicePort: event.target.value }))}
                  type="number"
                  value={form.aiServicePort}
                />
              }
              description={c.servicePortDesc}
              title={c.servicePort}
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
            {c.testAiService}
          </Button>
          <div className="mt-4">
            <StatusPanel result={aiStatus} />
          </div>
        </div>
      </details>

      <div className="mt-8">
        <SectionHeading icon={KeyRound} title={c.autoCountConnection} />
        <div className="grid gap-1">
          <ListRow
            action={
              <Input
                className={cn('h-8 font-mono', CONTROL_TEXT)}
                onChange={event => setForm(current => ({ ...current, cloudUrl: event.target.value }))}
                value={form.cloudUrl}
              />
            }
            description={c.cloudUrlDesc}
            title={c.cloudUrl}
          />
          <ListRow
            action={
              <div className="flex items-center gap-2">
                <Input
                  autoComplete="off"
                  className={cn('h-8 font-mono', CONTROL_TEXT)}
                  onChange={event => setForm(current => ({ ...current, apiKey: event.target.value }))}
                  placeholder={form.apiKeyConfigured ? c.existingKeyPlaceholder : c.enterApiKeyPlaceholder}
                  type={showApiKey ? 'text' : 'password'}
                  value={form.apiKey}
                />
                <Button
                  aria-label={showApiKey ? c.hideApiKey : c.revealApiKey}
                  onClick={() => setShowApiKey(value => !value)}
                  size="icon-sm"
                  type="button"
                  variant="outline"
                >
                  {showApiKey ? <EyeOff /> : <Eye />}
                </Button>
              </div>
            }
            description={c.apiKeyDesc}
            title={c.apiKey}
          />
          <ListRow
            action={
              <Input
                className={cn('h-8 font-mono', CONTROL_TEXT)}
                onChange={event => setForm(current => ({ ...current, connectorId: event.target.value }))}
                value={form.connectorId}
              />
            }
            description={c.connectorIdDesc}
            title={c.connectorId}
          />
          <ListRow
            action={
              <Input
                className={cn('h-8 font-mono', CONTROL_TEXT)}
                onChange={event => setForm(current => ({ ...current, companyId: event.target.value }))}
                value={form.companyId}
              />
            }
            description={c.companyIdDesc}
            title={c.companyId}
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
          {c.testAutoCount}
        </Button>
        <div className="mt-4">
          <StatusPanel result={autoCountStatus} />
        </div>
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-end gap-3 border-t border-(--ui-stroke-tertiary) pt-5">
        <p className="mr-auto max-w-xl text-xs leading-5 text-(--ui-text-tertiary)">{c.saveDesc}</p>
        <Button disabled={saving} onClick={() => void save()} size="sm">
          {saving ? <Loader2 className="animate-spin" /> : <Save />}
          {c.saveAndApply}
        </Button>
      </div>
    </SettingsContent>
  )
}
