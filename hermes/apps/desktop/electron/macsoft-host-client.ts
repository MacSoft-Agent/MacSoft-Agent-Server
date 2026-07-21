import fs from 'node:fs'

import type { MacSoftProductPaths } from './macsoft-product'

export type MacSoftServiceName = 'ai_service' | 'server'
export type MacSoftServiceAction = 'restart' | 'start' | 'stop'

export interface MacSoftConfigBackendConnection {
  baseUrl: string
  token: string
}

export interface MacSoftServiceStatus {
  last_error: null | string
  name: MacSoftServiceName
  owned: boolean
  pid: null | number
  started_at: null | number
  status: 'error' | 'running' | 'starting' | 'stopped'
}

export interface MacSoftHostStatus {
  auto_start: boolean
  product: 'MacSoft Agent'
  services: Record<MacSoftServiceName, MacSoftServiceStatus>
  version: string
}

interface ControlConfiguration {
  host: '127.0.0.1'
  port: number
  token: string
}

export const HOST_CONTROL_TIMEOUT_MS = 75_000
export const MACSOFT_CONFIG_BACKEND_PORT = 8643

function stoppedService(name: MacSoftServiceName): MacSoftServiceStatus {
  return { last_error: null, name, owned: false, pid: null, started_at: null, status: 'stopped' }
}

function hostNotRegisteredStatus(): MacSoftHostStatus {
  return {
    auto_start: false,
    product: 'MacSoft Agent',
    services: {
      ai_service: stoppedService('ai_service'),
      server: stoppedService('server')
    },
    version: 'unavailable'
  }
}

export class MacSoftHostClient {
  constructor(private readonly paths: MacSoftProductPaths, private readonly fetchImpl = globalThis.fetch) {}

  private configuration(): ControlConfiguration {
    let value: ControlConfiguration
    try {
      value = JSON.parse(fs.readFileSync(this.paths.hostControlFile, 'utf8')) as ControlConfiguration
    } catch (error) {
      const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : ''
      if (code === 'ENOENT') {
        throw new Error('MacSoft Agent Host is not registered or running yet.')
      }
      if (code === 'EACCES' || code === 'EPERM') {
        throw new Error('MacSoft Agent cannot read the Host control configuration. Check folder permissions.')
      }
      throw new Error('MacSoft Agent Host control configuration is invalid.')
    }
    if (
      !value ||
      value.host !== '127.0.0.1' ||
      !Number.isInteger(value.port) ||
      value.port < 1 ||
      value.port > 65_535 ||
      typeof value.token !== 'string' ||
      value.token.length < 32
    ) {
      throw new Error('MacSoft Agent Host control configuration is invalid.')
    }
    return value
  }

  private async request(pathname: string, init: RequestInit = {}): Promise<any> {
    const config = this.configuration()
    let response: Response
    try {
      response = await this.fetchImpl(`http://127.0.0.1:${config.port}${pathname}`, {
        ...init,
        headers: { ...init.headers, Authorization: `Bearer ${config.token}`, 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(HOST_CONTROL_TIMEOUT_MS)
      })
    } catch {
      throw new Error('MacSoft Agent Host is unavailable.')
    }
    const body = await response.json().catch(() => null)
    if (!response.ok || !body?.ok) throw new Error(body?.message || 'MacSoft Agent Host is unavailable.')
    return body
  }

  async status(): Promise<MacSoftHostStatus> {
    if (!fs.existsSync(this.paths.hostControlFile)) {
      return hostNotRegisteredStatus()
    }
    const body = await this.request('/v1/status')
    return body as MacSoftHostStatus
  }

  async pairingCode(): Promise<string> {
    const body = await this.request('/v1/pairing-code')
    const pairingCode = body?.pairing_code
    if (typeof pairingCode !== 'string' || !pairingCode.trim()) {
      throw new Error('MacSoft Agent Host returned an invalid pairing response.')
    }
    return pairingCode.trim()
  }

  configBackendConnection(): MacSoftConfigBackendConnection {
    const config = this.configuration()

    return {
      baseUrl: `http://127.0.0.1:${MACSOFT_CONFIG_BACKEND_PORT}`,
      token: config.token
    }
  }

  trustedHostToken(): string {
    return this.configuration().token
  }

  async serviceAction(name: MacSoftServiceName, action: MacSoftServiceAction): Promise<MacSoftServiceStatus> {
    const body = await this.request(`/v1/services/${name}/${action}`, { method: 'POST' })
    return body.service as MacSoftServiceStatus
  }

  async setAutoStart(enabled: boolean): Promise<boolean> {
    const body = await this.request('/v1/autostart', { method: 'POST', body: JSON.stringify({ enabled }) })
    return Boolean(body.auto_start)
  }
}
