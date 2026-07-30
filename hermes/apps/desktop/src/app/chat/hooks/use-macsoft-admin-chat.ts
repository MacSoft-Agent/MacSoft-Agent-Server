import { useCallback, useEffect, useReducer, useRef } from 'react'

import type { MacSoftAdminMessage, MacSoftAdminSession, MacSoftAdminStreamEvent } from '@/global'
import {
  appendAssistantTextPart,
  assistantTextPart,
  type ChatMessage,
  chatMessageText,
  textPart
} from '@/lib/chat-messages'
import type { SessionInfo } from '@/types/hermes'
import type { ComposerAttachment } from '@/store/composer'

export interface MacSoftAdminActivity {
  title: string
  detail?: string
}

export interface MacSoftAdminChatState {
  activity: MacSoftAdminActivity | null
  error: string | null
  historyLoading: boolean
  interrupting: boolean
  loading: boolean
  messages: ChatMessage[]
  selectedSessionId: string | null
  sessions: MacSoftAdminSession[]
  sessionsLoaded: boolean
  streamId: string | null
  streaming: boolean
}

export const initialMacSoftAdminChatState: MacSoftAdminChatState = {
  activity: null,
  error: null,
  historyLoading: false,
  interrupting: false,
  loading: false,
  messages: [],
  selectedSessionId: null,
  sessions: [],
  sessionsLoaded: false,
  streamId: null,
  streaming: false
}

type AdminAction =
  | { type: 'load-start' }
  | { type: 'sessions'; sessions: MacSoftAdminSession[]; selectedSessionId: string | null }
  | { type: 'select'; sessionId: string | null; messages: ChatMessage[]; run: ActiveRun | null }
  | { type: 'history-start' }
  | { type: 'history'; messages: ChatMessage[] }
  | { type: 'user-message'; message: ChatMessage }
  | { type: 'stream-start'; streamId: string }
  | { type: 'interrupt-start' }
  | { type: 'interrupt-error'; message: string }
  | { type: 'stream-event'; event: MacSoftAdminStreamEvent }
  | { type: 'stream-error'; message: string }
  | { type: 'error'; message: string }
  | { type: 'draft' }

interface ActiveRun {
  activity: MacSoftAdminActivity | null
  assistantMessageId: string
  interrupting: boolean
  streamId: string | null
}

const RECONCILE_DELAYS_MS = [100, 250, 500, 1_000]

export function messageFromServer(message: MacSoftAdminMessage): ChatMessage | null {
  if (message.role !== 'user' && message.role !== 'assistant') {
    return null
  }

  const content = typeof message.content === 'string' ? message.content : ''

  return {
    id: message.message_id || message.id,
    parts: [message.role === 'assistant' ? assistantTextPart(content) : textPart(content)],
    role: message.role,
    adminAttachments: (message.attachments ?? []).map(file => ({
      fileId: file.file_id,
      sessionId: message.session_id,
      filename: file.filename,
      contentType: file.content_type,
      sizeBytes: file.size_bytes
    })),
    timestamp: Date.parse(message.created_at) || undefined
  }
}

export function sessionFromServer(session: MacSoftAdminSession): SessionInfo {
  const startedAt = Date.parse(session.created_at) || Date.now()
  const lastActive = Date.parse(session.updated_at) || startedAt

  return {
    archived: false,
    cwd: null,
    ended_at: null,
    id: session.session_id,
    input_tokens: 0,
    is_active: false,
    last_active: lastActive,
    message_count: 0,
    model: null,
    output_tokens: 0,
    preview: null,
    source: 'desktop',
    started_at: startedAt,
    title: session.title || null,
    tool_call_count: 0
  }
}

function safeError(message: unknown, fallback: string) {
  return typeof message === 'string' && message.length > 0 && message.length < 240 ? message : fallback
}

function streamEventData(event: MacSoftAdminStreamEvent): Record<string, unknown> | null {
  return event && typeof event.data === 'object' && event.data !== null ? event.data : null
}

function viewFromRun(run: ActiveRun | null) {
  return {
    activity: run?.activity ?? null,
    interrupting: run?.interrupting ?? false,
    streamId: run?.streamId ?? null,
    streaming: Boolean(run)
  }
}

export function reduceMacSoftAdminChat(state: MacSoftAdminChatState, action: AdminAction): MacSoftAdminChatState {
  switch (action.type) {
    case 'load-start':
      return { ...state, error: null, loading: true }

    case 'sessions':
      return {
        ...state,
        error: null,
        loading: false,
        selectedSessionId: action.selectedSessionId,
        sessions: action.sessions,
        sessionsLoaded: true
      }

    case 'select':
      return {
        ...state,
        error: null,
        historyLoading: false,
        messages: action.messages,
        selectedSessionId: action.sessionId,
        ...viewFromRun(action.run)
      }

    case 'history-start':
      return { ...state, error: null, historyLoading: true }

    case 'history':
      return { ...state, historyLoading: false, messages: action.messages }

    case 'user-message':
      return { ...state, error: null, messages: [...state.messages, action.message] }

    case 'stream-start':
      return { ...state, activity: null, error: null, interrupting: false, streamId: action.streamId, streaming: true }

    case 'interrupt-start':
      return { ...state, error: null, interrupting: true }

    case 'interrupt-error':
      return { ...state, error: action.message, interrupting: false }

    case 'stream-error':
      return { ...state, activity: null, error: action.message, interrupting: false, streamId: null, streaming: false }

    case 'error':
      return { ...state, error: action.message, historyLoading: false, loading: false }

    case 'draft':
      return {
        ...state,
        activity: null,
        error: null,
        historyLoading: false,
        interrupting: false,
        messages: [],
        selectedSessionId: null,
        streamId: null,
        streaming: false
      }
    case 'stream-event': {
      const data = streamEventData(action.event)

      if (!data || action.event.streamId !== state.streamId) {
        return state
      }

      if (action.event.event === 'activity') {
        return {
          ...state,
          activity: {
            detail: typeof data.detail === 'string' ? data.detail : undefined,
            title: typeof data.title === 'string' ? data.title : 'MacSoft Agent is processing the request.'
          }
        }
      }

      if (action.event.event === 'error') {
        return {
          ...state,
          activity: null,
          error: safeError(data.message, 'MacSoft Server could not complete the request.'),
          interrupting: false,
          streamId: null,
          streaming: false
        }
      }

      if (action.event.event === 'message_done') {
        return { ...state, activity: null, interrupting: false, streamId: null, streaming: false }
      }

      return state
    }
  }
}

export function macSoftAdminPromptCapabilities(state: MacSoftAdminChatState, serverReady: boolean) {
  const canEditPrompt = serverReady && !state.historyLoading

  return {
    canEditPrompt,
    canSubmitPrompt: canEditPrompt && !state.streaming && !state.loading
  }
}

export function reconcileAdminMessages(local: ChatMessage[], persisted: ChatMessage[]): ChatMessage[] {
  if (persisted.length === 0 && local.length > 0) {
    return local
  }

  if (persisted.length < local.length) {
    return local
  }

  for (let index = 0; index < local.length; index += 1) {
    const localMessage = local[index]
    const persistedMessage = persisted[index]

    if (!persistedMessage || persistedMessage.role !== localMessage.role) {
      return local
    }

    if (chatMessageText(persistedMessage).length < chatMessageText(localMessage).length) {
      return local
    }
  }

  return persisted
}

export type MacSoftAdminChatController = ReturnType<typeof useMacSoftAdminChat>

async function uploadAdminAttachments(sessionId: string, attachments: ComposerAttachment[]) {
  const uploadable = attachments.filter(attachment => attachment.kind === 'image' || attachment.kind === 'file')
  if (uploadable.length !== attachments.length) {
    throw new Error('Admin chat supports image and file attachments only.')
  }
  return Promise.all(uploadable.map(async attachment => {
    if (!attachment.path) throw new Error(`Admin attachment ${attachment.label} could not be read.`)
    const dataUrl = await window.hermesDesktop.readFileDataUrl(attachment.path)
    const uploaded = await window.hermesDesktop.macSoftAdminChat.uploadFile({
      dataUrl,
      filename: attachment.label,
      sessionId
    })
    return uploaded
  }))
}

export function useMacSoftAdminChat(enabled: boolean, serverReady: boolean) {
  const [state, dispatch] = useReducer(reduceMacSoftAdminChat, initialMacSoftAdminChatState)
  const selectedSessionRef = useRef<string | null>(null)
  const sessionsRef = useRef<MacSoftAdminSession[]>([])
  const messagesBySessionRef = useRef(new Map<string, ChatMessage[]>())
  const runsBySessionRef = useRef(new Map<string, ActiveRun>())
  const reconcileGenerationRef = useRef(new Map<string, number>())

  const updateSessionMessages = useCallback(
    (sessionId: string, update: (messages: ChatMessage[]) => ChatMessage[]) => {
      const next = update(messagesBySessionRef.current.get(sessionId) ?? [])
      messagesBySessionRef.current.set(sessionId, next)

      if (selectedSessionRef.current === sessionId) {
        dispatch({ type: 'history', messages: next })
      }

      return next
    },
    []
  )

  const syncSelectedView = useCallback((sessionId: string | null) => {
    if (selectedSessionRef.current !== sessionId) {
      return
    }

    dispatch({
      type: 'select',
      messages: sessionId ? (messagesBySessionRef.current.get(sessionId) ?? []) : [],
      run: sessionId ? (runsBySessionRef.current.get(sessionId) ?? null) : null,
      sessionId
    })
  }, [])

  const readHistory = useCallback(async (sessionId: string) => {
    const messages = await window.hermesDesktop.macSoftAdminChat.getMessages(sessionId)

    return messages.map(messageFromServer).filter((message): message is ChatMessage => message !== null)
  }, [])

  const reconcileHistory = useCallback(
    async (sessionId: string, generation: number, attempt = 0): Promise<void> => {
      if (reconcileGenerationRef.current.get(sessionId) !== generation || runsBySessionRef.current.has(sessionId)) {
        return
      }

      try {
        const persisted = await readHistory(sessionId)

        if (reconcileGenerationRef.current.get(sessionId) !== generation || runsBySessionRef.current.has(sessionId)) {
          return
        }

        const local = messagesBySessionRef.current.get(sessionId) ?? []
        const next = reconcileAdminMessages(local, persisted)

        if (next === local && persisted.length < local.length && attempt < RECONCILE_DELAYS_MS.length) {
          await new Promise(resolve => window.setTimeout(resolve, RECONCILE_DELAYS_MS[attempt]))
          await reconcileHistory(sessionId, generation, attempt + 1)

          return
        }

        messagesBySessionRef.current.set(sessionId, next)

        if (selectedSessionRef.current === sessionId) {
          dispatch({ type: 'history', messages: next })
        }
      } catch {
        // The completed local transcript remains authoritative until a later open/reload can reconcile it.
      }
    },
    [readHistory]
  )

  const scheduleHistoryReconcile = useCallback(
    (sessionId: string) => {
      const generation = (reconcileGenerationRef.current.get(sessionId) ?? 0) + 1
      reconcileGenerationRef.current.set(sessionId, generation)
      void reconcileHistory(sessionId, generation)
    },
    [reconcileHistory]
  )

  const selectSession = useCallback(
    async (sessionId: string) => {
      if (!sessionId || !sessionsRef.current.some(session => session.session_id === sessionId)) {
        return false
      }

      if (selectedSessionRef.current === sessionId) {
        syncSelectedView(sessionId)

        return true
      }

      selectedSessionRef.current = sessionId
      localStorage.setItem('macsoft.admin.selected-session', sessionId)
      syncSelectedView(sessionId)

      if (messagesBySessionRef.current.has(sessionId) || runsBySessionRef.current.has(sessionId)) {
        return true
      }

      dispatch({ type: 'history-start' })

      try {
        const messages = await readHistory(sessionId)

        if (runsBySessionRef.current.has(sessionId)) {
          return true
        }

        messagesBySessionRef.current.set(sessionId, messages)

        if (selectedSessionRef.current === sessionId) {
          dispatch({ type: 'history', messages })
        }

        return true
      } catch {
        if (selectedSessionRef.current === sessionId) {
          dispatch({ type: 'error', message: 'Admin chat history could not be loaded.' })
        }

        return false
      }
    },
    [readHistory, syncSelectedView]
  )

  const createSession = useCallback(async () => {
    if (selectedSessionRef.current && runsBySessionRef.current.has(selectedSessionRef.current)) {
      return false
    }

    try {
      const session = await window.hermesDesktop.macSoftAdminChat.createSession()
      sessionsRef.current = [...sessionsRef.current, session]
      messagesBySessionRef.current.set(session.session_id, [])
      selectedSessionRef.current = session.session_id
      localStorage.setItem('macsoft.admin.selected-session', session.session_id)
      dispatch({ type: 'sessions', selectedSessionId: session.session_id, sessions: sessionsRef.current })
      syncSelectedView(session.session_id)

      return true
    } catch {
      dispatch({ type: 'error', message: 'Admin session could not be created.' })

      return false
    }
  }, [syncSelectedView])

  const deleteSession = useCallback(
    async (sessionId: string) => {
      if (runsBySessionRef.current.has(sessionId)) {
        return false
      }

      try {
        await window.hermesDesktop.macSoftAdminChat.deleteSession(sessionId)
        sessionsRef.current = sessionsRef.current.filter(session => session.session_id !== sessionId)
        messagesBySessionRef.current.delete(sessionId)
        reconcileGenerationRef.current.delete(sessionId)

        if (selectedSessionRef.current !== sessionId) {
          dispatch({ type: 'sessions', selectedSessionId: selectedSessionRef.current, sessions: sessionsRef.current })

          return true
        }

        selectedSessionRef.current = null
        localStorage.removeItem('macsoft.admin.selected-session')
        dispatch({ type: 'sessions', selectedSessionId: null, sessions: sessionsRef.current })
        syncSelectedView(null)

        return true
      } catch {
        dispatch({ type: 'error', message: 'Admin session could not be deleted.' })

        return false
      }
    },
    [syncSelectedView]
  )

  const startFreshDraft = useCallback(() => {
    const currentSessionId = selectedSessionRef.current

    if (currentSessionId && runsBySessionRef.current.has(currentSessionId)) {
      return false
    }

    selectedSessionRef.current = null
    localStorage.removeItem('macsoft.admin.selected-session')
    dispatch({ type: 'draft' })

    return true
  }, [])

  const submit = useCallback(
    async (value: string, attachments: ComposerAttachment[] = []) => {
      const message = value.trim()

      if (!enabled || !serverReady || !message) {
        return false
      }

      let sessionId = selectedSessionRef.current

      if (sessionId && runsBySessionRef.current.has(sessionId)) {
        return false
      }

      try {
        if (!sessionId) {
          const session = await window.hermesDesktop.macSoftAdminChat.createSession()
          sessionId = session.session_id
          sessionsRef.current = [...sessionsRef.current, session]
          messagesBySessionRef.current.set(sessionId, [])
          selectedSessionRef.current = sessionId
          localStorage.setItem('macsoft.admin.selected-session', sessionId)
          dispatch({ type: 'sessions', selectedSessionId: sessionId, sessions: sessionsRef.current })
        }

        const now = Date.now()
        const assistantMessageId = `temporary-assistant-${sessionId}-${now}`

        const userMessage: ChatMessage = {
          id: `temporary-user-${sessionId}-${now}`,
          parts: [textPart(message)],
          role: 'user',
          timestamp: now
        }

        const assistantMessage: ChatMessage = {
          id: assistantMessageId,
          parts: [],
          pending: true,
          role: 'assistant',
          timestamp: now
        }

        const run: ActiveRun = {
          activity: null,
          assistantMessageId,
          interrupting: false,
          streamId: null
        }

        runsBySessionRef.current.set(sessionId, run)
        updateSessionMessages(sessionId, current => [...current, userMessage, assistantMessage])
        syncSelectedView(sessionId)

        const uploadedFiles = await uploadAdminAttachments(sessionId, attachments)
        updateSessionMessages(sessionId, current => current.map(item => item.id === userMessage.id ? {
          ...item,
          adminAttachments: uploadedFiles.map(file => ({
            fileId: file.file_id,
            sessionId: file.session_id,
            filename: file.filename,
            contentType: file.content_type,
            sizeBytes: file.size_bytes
          }))
        } : item))
        const result = await window.hermesDesktop.macSoftAdminChat.startStream({ message, sessionId, uploadedFileIds: uploadedFiles.map(file => file.file_id) })

        if (runsBySessionRef.current.get(sessionId) !== run) {
          return false
        }

        run.streamId = result.streamId
        syncSelectedView(sessionId)

        return true
      } catch {
        if (sessionId) {
          const run = runsBySessionRef.current.get(sessionId)

          if (run) {
            runsBySessionRef.current.delete(sessionId)
            updateSessionMessages(sessionId, current =>
              current.map(item =>
                item.id === run.assistantMessageId
                  ? { ...item, error: 'Admin chat could not start.', pending: false }
                  : item
              )
            )
            syncSelectedView(sessionId)
          }
        }

        dispatch({ type: 'stream-error', message: 'Admin chat could not start.' })

        return false
      }
    },
    [enabled, serverReady, syncSelectedView, updateSessionMessages]
  )

  const stop = useCallback(async () => {
    const sessionId = selectedSessionRef.current
    const run = sessionId ? runsBySessionRef.current.get(sessionId) : undefined

    if (!enabled || !sessionId || !run?.streamId || run.interrupting) {
      return
    }

    run.interrupting = true
    syncSelectedView(sessionId)

    try {
      await window.hermesDesktop.macSoftAdminChat.stopStream({ sessionId, streamId: run.streamId })
    } catch {
      run.interrupting = false
      syncSelectedView(sessionId)
      dispatch({ type: 'interrupt-error', message: 'Admin chat could not be interrupted.' })
    }
  }, [enabled, syncSelectedView])

  useEffect(() => {
    if (!enabled || !serverReady) {
      return
    }

    let cancelled = false
    dispatch({ type: 'load-start' })

    void window.hermesDesktop.macSoftAdminChat
      .listSessions()
      .then(sessions => {
        if (cancelled) {
          return
        }

        sessionsRef.current = sessions
        dispatch({ type: 'sessions', selectedSessionId: selectedSessionRef.current, sessions })
      })
      .catch(() => {
        if (!cancelled) {
          dispatch({ type: 'error', message: 'MacSoft Server Admin authentication is unavailable.' })
        }
      })

    return () => {
      cancelled = true
    }
  }, [enabled, serverReady])

  useEffect(() => {
    if (!enabled) {
      return
    }

    return window.hermesDesktop.macSoftAdminChat.onStreamEvent(event => {
      const data = streamEventData(event)

      if (!data) {
        return
      }

      const runEntry = [...runsBySessionRef.current.entries()].find(([, run]) => run.streamId === event.streamId)

      if (!runEntry) {
        return
      }

      const [sessionId, run] = runEntry

      if (event.event === 'message_start') {
        const messageId = typeof data.message_id === 'string' ? data.message_id : ''

        if (messageId) {
          const previousId = run.assistantMessageId
          run.assistantMessageId = messageId
          updateSessionMessages(sessionId, current =>
            current.map(message => (message.id === previousId ? { ...message, id: messageId } : message))
          )
        }

        return
      }

      if (event.event === 'activity') {
        run.activity = {
          detail: typeof data.detail === 'string' ? data.detail : undefined,
          title: typeof data.title === 'string' ? data.title : 'MacSoft Agent is processing the request.'
        }
        syncSelectedView(sessionId)

        return
      }

      if (event.event === 'token_delta') {
        const delta = typeof data.text === 'string' ? data.text : ''

        if (!delta) {
          return
        }

        run.activity = null
        updateSessionMessages(sessionId, current =>
          current.map(message =>
            message.id === run.assistantMessageId
              ? { ...message, parts: appendAssistantTextPart(message.parts, delta) }
              : message
          )
        )
        syncSelectedView(sessionId)

        return
      }

      if (event.event === 'message_done' || event.event === 'error') {
        const failed = event.event === 'error' || data.ok === false
        const error = failed ? safeError(data.message, 'MacSoft Server could not complete the request.') : undefined

        updateSessionMessages(sessionId, current =>
          current.map(message =>
            message.id === run.assistantMessageId ? { ...message, error, pending: false } : message
          )
        )
        runsBySessionRef.current.delete(sessionId)
        syncSelectedView(sessionId)

        if (failed && selectedSessionRef.current === sessionId) {
          dispatch({ type: 'stream-error', message: error ?? 'Admin chat did not complete successfully.' })
        }

        scheduleHistoryReconcile(sessionId)
      }
    })
  }, [enabled, scheduleHistoryReconcile, syncSelectedView, updateSessionMessages])

  return {
    ...state,
    createSession,
    deleteSession,
    selectSession,
    startFreshDraft,
    stop,
    submit,
    ...macSoftAdminPromptCapabilities(state, serverReady)
  }
}
