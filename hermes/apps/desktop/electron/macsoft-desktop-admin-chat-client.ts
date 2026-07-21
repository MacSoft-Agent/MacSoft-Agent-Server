const ADMIN_SERVER_BASE_URL = 'http://127.0.0.1:8787'
const ADMIN_REQUEST_TIMEOUT_MS = 10_000
const ADMIN_STREAM_TIMEOUT_MS = 30 * 60 * 1_000

interface TrustedHostTokenProvider {
  trustedHostToken: () => string
}

export interface AdminSessionSummary {
  id: string
  session_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface AdminMessage {
  id: string
  message_id: string
  session_id: string
  role: string
  content: string
  status: string
  model: string | null
  created_at: string
}

export class MacSoftDesktopAdminChatClient {
  private adminAccessToken: string | null = null

  constructor(
    private readonly hostTokenProvider: TrustedHostTokenProvider,
    private readonly fetchImpl: typeof fetch = globalThis.fetch,
    private readonly timeoutMs = ADMIN_REQUEST_TIMEOUT_MS
  ) {}

  async ensureAdminAccess(): Promise<void> {
    if (this.adminAccessToken) {
      return
    }
    const hostToken = this.hostTokenProvider.trustedHostToken()
    const response = await this.fetchImpl(`${ADMIN_SERVER_BASE_URL}/api/internal/desktop-admin/auth/session`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${hostToken}`, Accept: 'application/json' },
      signal: AbortSignal.timeout(this.timeoutMs)
    })
    const body = await this.readJson(response)
    if (!response.ok || typeof body?.access_token !== 'string') {
      throw new Error('MacSoft Server Admin authentication is unavailable.')
    }
    this.adminAccessToken = body.access_token
  }

  async listAdminSessions(): Promise<AdminSessionSummary[]> {
    const body = await this.requestJson('/api/admin/sessions', { method: 'GET' })
    return Array.isArray(body?.sessions) ? (body.sessions as AdminSessionSummary[]) : []
  }

  async createAdminSession(title = 'New Admin Chat'): Promise<AdminSessionSummary> {
    const body = await this.requestJson('/api/admin/sessions', {
      method: 'POST',
      body: JSON.stringify({ title })
    })
    if (!body?.session) throw new Error('MacSoft Server returned an invalid Admin session.')
    return body.session as AdminSessionSummary
  }

  async readAdminMessages(sessionId: string): Promise<AdminMessage[]> {
    const body = await this.requestJson(`/api/admin/sessions/${encodeURIComponent(sessionId)}/messages`, { method: 'GET' })
    return Array.isArray(body?.messages) ? (body.messages as AdminMessage[]) : []
  }

  async deleteAdminSession(sessionId: string): Promise<void> {
    await this.requestJson(`/api/admin/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
  }

  async startAdminChatStream(sessionId: string, message: string, signal?: AbortSignal): Promise<Response> {
    return this.requestStream('/api/admin/chat/stream', { session_id: sessionId, message, uploaded_file_ids: [] }, signal)
  }

  private async requestJson(pathname: string, init: RequestInit): Promise<any> {
    const response = await this.request(pathname, init)
    return this.readJson(response)
  }

  private async requestStream(pathname: string, payload: unknown, signal?: AbortSignal): Promise<Response> {
    return this.request(pathname, {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { Accept: 'text/event-stream' },
      signal
    }, ADMIN_STREAM_TIMEOUT_MS)
  }

  private async request(pathname: string, init: RequestInit, timeoutMs = this.timeoutMs): Promise<Response> {
    await this.ensureAdminAccess()
    let response = await this.send(pathname, init, timeoutMs)
    if (response.status === 401) {
      this.adminAccessToken = null
      await this.ensureAdminAccess()
      response = await this.send(pathname, init, timeoutMs)
    }
    if (!response.ok) {
      throw new Error('MacSoft Server Admin request failed.')
    }
    return response
  }

  private async send(pathname: string, init: RequestInit, timeoutMs: number): Promise<Response> {
    return this.fetchImpl(`${ADMIN_SERVER_BASE_URL}${pathname}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...init.headers,
        Authorization: `Bearer ${this.adminAccessToken ?? ''}`
      },
      signal: init.signal ?? AbortSignal.timeout(timeoutMs)
    })
  }

  private async readJson(response: Response): Promise<any> {
    return response.json().catch(() => null)
  }
}
