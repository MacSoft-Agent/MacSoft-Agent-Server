export type MacSoftDesktopChatStatus = 'idle' | 'connecting' | 'ready' | 'unavailable' | 'error'

export interface MacSoftDesktopChatStatusResult {
  status: MacSoftDesktopChatStatus
  message?: string
}

export const MACSOFT_SERVER_HEALTH_URL = 'http://127.0.0.1:8787/health'
export const MACSOFT_SERVER_HEALTH_TIMEOUT_MS = 2_500

export class MacSoftDesktopChatClient {
  constructor(
    private readonly fetchImpl: typeof fetch = globalThis.fetch,
    private readonly timeoutMs = MACSOFT_SERVER_HEALTH_TIMEOUT_MS
  ) {}

  async getStatus(): Promise<MacSoftDesktopChatStatusResult> {
    try {
      const response = await this.fetchImpl(MACSOFT_SERVER_HEALTH_URL, {
        method: 'GET',
        signal: AbortSignal.timeout(this.timeoutMs)
      })

      if (!response.ok) {
        return { status: 'unavailable', message: 'MacSoft Server is unavailable.' }
      }

      return { status: 'ready' }
    } catch {
      // Keep transport details and local paths out of the renderer contract.
      return { status: 'unavailable', message: 'MacSoft Server is unavailable.' }
    }
  }
}
