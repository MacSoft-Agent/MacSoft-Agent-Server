import { useEffect, useState } from 'react'

export type MacSoftDesktopChatStatus = 'idle' | 'connecting' | 'ready' | 'unavailable' | 'error'

const STATUS_POLL_INTERVAL_MS = 5_000

export function resolveMacSoftPromptCapabilities(
  customerRuntime: boolean,
  status: MacSoftDesktopChatStatus,
  gatewayOpen: boolean
) {
  return {
    canEditPrompt: customerRuntime ? status === 'ready' : gatewayOpen,
    canSubmitPrompt: customerRuntime ? false : gatewayOpen
  }
}

export function useMacSoftDesktopChatStatus(enabled: boolean) {
  const [status, setStatus] = useState<MacSoftDesktopChatStatus>(enabled ? 'connecting' : 'idle')
  const [message, setMessage] = useState<string | undefined>()

  useEffect(() => {
    if (!enabled) {
      setStatus('idle')
      setMessage(undefined)
      return
    }

    let cancelled = false

    const probe = async () => {
      setStatus(current => (current === 'ready' ? 'ready' : 'connecting'))
      try {
        const result = await window.hermesDesktop?.macSoftDesktopChat?.getStatus()

        if (!result) {
          throw new Error('Desktop chat status bridge unavailable')
        }

        if (!cancelled) {
          setStatus(result.status)
          setMessage(result.message)
        }
      } catch {
        if (!cancelled) {
          setStatus('error')
          setMessage('MacSoft Server status is unavailable.')
        }
      }
    }

    void probe()
    const timer = window.setInterval(() => void probe(), STATUS_POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [enabled])

  return { status, message }
}
