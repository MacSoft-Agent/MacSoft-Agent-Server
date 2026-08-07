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
  session_type: 'chat' | 'global_training'
  workflow_target: string
  created_at: string
  updated_at: string
}

export interface GlobalLearningProposal {
  proposal_id: string
  training_session_id: string
  run_id: string | null
  kind: string
  workflow_target: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  decided_at: string | null
  previous_hash: string | null
  new_hash: string | null
  changes: Array<{
    path: string
    action: 'create' | 'update' | 'delete'
    previous_hash: string | null
    new_hash: string | null
  }>
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

export interface AdminUploadedFile {
  file_id: string
  fileId: string
  session_id: string
  sessionId: string
  filename: string
  content_type: string
  contentType: string
  size_bytes: number
  sizeBytes: number
  sha256: string
  created_at: string
  createdAt: string
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

  async createGlobalTrainingSession(workflowTarget = 'general'): Promise<AdminSessionSummary> {
    const body = await this.requestJson('/api/admin/global-learning/sessions', {
      method: 'POST', body: JSON.stringify({ workflow_target: workflowTarget })
    })
    if (!body?.session) throw new Error('MacSoft Server returned an invalid Global Training session.')
    return body.session as AdminSessionSummary
  }

  async globalLearningStatus(sessionId: string): Promise<{ enabled: boolean; session_id: string | null }> {
    const body = await this.requestJson(
      `/api/admin/global-learning/status?session_id=${encodeURIComponent(sessionId)}`,
      { method: 'GET' }
    )
    return { enabled: body?.enabled === true, session_id: typeof body?.session_id === 'string' ? body.session_id : null }
  }

  async toggleGlobalLearning(sessionId: string, enabled: boolean): Promise<{ enabled: boolean }> {
    const body = await this.requestJson('/api/admin/global-learning/toggle', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        enabled,
        confirmation: enabled ? 'ENABLE GLOBAL LEARNING' : ''
      })
    })
    return { enabled: body?.enabled === true }
  }

  async listGlobalLearningProposals(): Promise<GlobalLearningProposal[]> {
    const body = await this.requestJson('/api/admin/global-learning/proposals', { method: 'GET' })
    return Array.isArray(body?.proposals) ? body.proposals as GlobalLearningProposal[] : []
  }

  async refreshGlobalLearningProposal(sessionId: string): Promise<GlobalLearningProposal | null> {
    const body = await this.requestJson('/api/admin/global-learning/proposals/refresh', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId })
    })
    return body?.proposal ? body.proposal as GlobalLearningProposal : null
  }

  async decideGlobalLearningProposal(proposalId: string, decision: 'approve' | 'reject'): Promise<GlobalLearningProposal> {
    const body = await this.requestJson(
      `/api/admin/global-learning/proposals/${encodeURIComponent(proposalId)}/${decision}`,
      { method: 'POST' }
    )
    if (!body?.proposal) throw new Error('MacSoft Server returned an invalid Global Learning proposal.')
    return body.proposal as GlobalLearningProposal
  }

  async restoreGlobalLearningProposal(proposalId: string): Promise<GlobalLearningProposal> {
    const body = await this.requestJson(
      `/api/admin/global-learning/proposals/${encodeURIComponent(proposalId)}/restore`,
      { method: 'POST' }
    )
    if (!body?.proposal || body?.restored !== true) {
      throw new Error('MacSoft Server could not restore this Global Learning proposal.')
    }
    return body.proposal as GlobalLearningProposal
  }

  async readAdminMessages(sessionId: string): Promise<AdminMessage[]> {
    const body = await this.requestJson(`/api/admin/sessions/${encodeURIComponent(sessionId)}/messages`, { method: 'GET' })
    return Array.isArray(body?.messages) ? (body.messages as AdminMessage[]) : []
  }

  async deleteAdminSession(sessionId: string): Promise<void> {
    await this.requestJson(`/api/admin/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
  }

  async uploadAdminFile(sessionId: string, file: { dataUrl: string; filename: string }): Promise<AdminUploadedFile> {
    const blob = dataUrlToBlob(file.dataUrl)
    const form = new FormData()
    form.set('file', blob, file.filename)
    const body = await this.requestJson(`/api/admin/sessions/${encodeURIComponent(sessionId)}/files`, {
      method: 'POST',
      body: form
    })
    if (!body?.file_id || !body?.session_id) throw new Error('MacSoft Server returned an invalid Admin file.')
    return body as AdminUploadedFile
  }

  async readAdminFileDataUrl(sessionId: string, fileId: string): Promise<string> {
    const response = await this.request(`/api/admin/sessions/${encodeURIComponent(sessionId)}/files/${encodeURIComponent(fileId)}`, { method: 'GET' })
    if (!response.ok) throw new Error('Admin attachment is unavailable.')
    const bytes = Buffer.from(await response.arrayBuffer())
    const mimeType = response.headers.get('content-type')?.split(';')[0] || 'application/octet-stream'
    return `data:${mimeType};base64,${bytes.toString('base64')}`
  }

  async startAdminChatStream(sessionId: string, message: string, uploadedFileIds: string[] = [], signal?: AbortSignal): Promise<Response> {
    return this.requestStream('/api/admin/chat/stream', { session_id: sessionId, message, uploaded_file_ids: uploadedFileIds }, signal)
  }

  async interruptAdminChat(sessionId: string): Promise<void> {
    await this.requestJson('/api/admin/chat/interrupt', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId })
    })
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
        ...init.headers,
        Authorization: `Bearer ${this.adminAccessToken ?? ''}`,
        ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' })
      },
      signal: init.signal ?? AbortSignal.timeout(timeoutMs)
    })
  }

  private async readJson(response: Response): Promise<any> {
    return response.json().catch(() => null)
  }
}

function dataUrlToBlob(dataUrl: string): Blob {
  const match = /^data:([^;,]+);base64,([A-Za-z0-9+/=]+)$/.exec(dataUrl)
  if (!match) throw new Error('Admin attachment is invalid.')
  return new Blob([Buffer.from(match[2], 'base64')], { type: match[1] })
}
