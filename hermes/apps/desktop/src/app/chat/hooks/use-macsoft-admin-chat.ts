import { useCallback, useEffect, useReducer, useRef } from 'react'

import type { MacSoftAdminMessage, MacSoftAdminSession, MacSoftAdminStreamEvent } from '@/global'

export interface MacSoftAdminUiMessage {
  id: string
  role: 'assistant' | 'user'
  content: string
  temporary?: boolean
}

export interface MacSoftAdminActivity {
  title: string
  detail?: string
}

export interface MacSoftAdminChatState {
  error: string | null
  historyLoading: boolean
  interrupting: boolean
  messages: MacSoftAdminUiMessage[]
  sessions: MacSoftAdminSession[]
  selectedSessionId: string | null
  streamId: string | null
  streaming: boolean
  activity: MacSoftAdminActivity | null
  loading: boolean
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
  streamId: null,
  streaming: false
}

type AdminAction =
  | { type: 'load-start' }
  | { type: 'sessions'; sessions: MacSoftAdminSession[]; selectedSessionId: string | null }
  | { type: 'history-start' }
  | { type: 'history'; messages: MacSoftAdminUiMessage[] }
  | { type: 'user-message'; message: MacSoftAdminUiMessage }
  | { type: 'stream-start'; streamId: string }
  | { type: 'interrupt-start' }
  | { type: 'interrupt-error'; message: string }
  | { type: 'stream-event'; event: MacSoftAdminStreamEvent }
  | { type: 'stream-error'; message: string }
  | { type: 'error'; message: string }

function messageFromServer(message: MacSoftAdminMessage): MacSoftAdminUiMessage | null {
  if (message.role !== 'user' && message.role !== 'assistant') return null
  return { content: typeof message.content === 'string' ? message.content : '', id: message.message_id || message.id, role: message.role }
}

function safeError(message: unknown, fallback: string) {
  return typeof message === 'string' && message.length > 0 && message.length < 240 ? message : fallback
}

function streamEventData(event: MacSoftAdminStreamEvent): Record<string, unknown> | null {
  return event && typeof event.data === 'object' && event.data !== null ? event.data : null
}

export function reduceMacSoftAdminChat(state: MacSoftAdminChatState, action: AdminAction): MacSoftAdminChatState {
  switch (action.type) {
    case 'load-start':
      return { ...state, error: null, loading: true }
    case 'sessions':
      return { ...state, error: null, loading: false, selectedSessionId: action.selectedSessionId, sessions: action.sessions }
    case 'history-start':
      return { ...state, activity: null, error: null, historyLoading: true, interrupting: false, messages: [], streamId: null, streaming: false }
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
      return { ...state, error: action.message, loading: false, historyLoading: false }
    case 'stream-event': {
      const event = action.event
      const data = streamEventData(event)
      if (!data || event.streamId !== state.streamId) return state
      if (event.event === 'message_start') return { ...state, streaming: true }
      if (event.event === 'activity') {
        const title = typeof data.title === 'string' ? data.title : 'MacSoft Agent is processing the request.'
        const detail = typeof data.detail === 'string' ? data.detail : undefined
        return { ...state, activity: { title, detail } }
      }
      if (event.event === 'token_delta') {
        const delta = typeof data.text === 'string' ? data.text : ''
        if (!delta) return state
        const id = `temporary-assistant-${state.streamId}`
        const existing = state.messages.find(message => message.id === id)
        return {
          ...state,
          messages: existing
            ? state.messages.map(message => (message.id === id ? { ...message, content: message.content + delta } : message))
            : [...state.messages, { content: delta, id, role: 'assistant', temporary: true }]
        }
      }
      if (event.event === 'error') {
        return { ...state, activity: null, error: safeError(data.message, 'MacSoft Server could not complete the request.'), interrupting: false, streamId: null, streaming: false }
      }
      if (event.event === 'message_done') return { ...state, activity: null, interrupting: false, streamId: null, streaming: false }
      return state
    }
  }
}

let activeRendererAdminStreamId: string | null = null

export function macSoftAdminPromptCapabilities(state: MacSoftAdminChatState, serverReady: boolean) {
  const canEditPrompt = serverReady && Boolean(state.selectedSessionId) && !state.historyLoading
  return {
    canEditPrompt,
    canSubmitPrompt: canEditPrompt && !state.streaming && !state.loading
  }
}

export function useMacSoftAdminChat(enabled: boolean, serverReady: boolean) {
  const [state, dispatch] = useReducer(reduceMacSoftAdminChat, initialMacSoftAdminChatState)
  const selectedSessionRef = useRef<string | null>(null)
  const streamIdRef = useRef<string | null>(null)
  const interruptingRef = useRef(false)
  selectedSessionRef.current = state.selectedSessionId
  streamIdRef.current = state.streamId
  interruptingRef.current = state.interrupting

  const loadHistory = useCallback(async (sessionId: string) => {
    dispatch({ type: 'history-start' })
    try {
      const messages = await window.hermesDesktop.macSoftAdminChat.getMessages(sessionId)
      dispatch({ type: 'history', messages: messages.map(messageFromServer).filter((message): message is MacSoftAdminUiMessage => message !== null) })
    } catch {
      dispatch({ type: 'error', message: 'Admin chat history could not be loaded.' })
    }
  }, [])

  const selectSession = useCallback(
    async (sessionId: string) => {
      if (state.streaming || !state.sessions.some(session => session.session_id === sessionId)) return false
      localStorage.setItem('macsoft.admin.selected-session', sessionId)
      selectedSessionRef.current = sessionId
      dispatch({ type: 'sessions', selectedSessionId: sessionId, sessions: state.sessions })
      await loadHistory(sessionId)
      return true
    },
    [loadHistory, state.sessions, state.streaming]
  )

  const createSession = useCallback(async () => {
    if (state.streaming) return false
    try {
      const session = await window.hermesDesktop.macSoftAdminChat.createSession()
      const sessions = [...state.sessions, session]
      localStorage.setItem('macsoft.admin.selected-session', session.session_id)
      dispatch({ type: 'sessions', selectedSessionId: session.session_id, sessions })
      await loadHistory(session.session_id)
      return true
    } catch {
      dispatch({ type: 'error', message: 'Admin session could not be created.' })
      return false
    }
  }, [loadHistory, state.sessions, state.streaming])

  const deleteSession = useCallback(
    async (sessionId: string) => {
      if (state.streaming) return false
      try {
        await window.hermesDesktop.macSoftAdminChat.deleteSession(sessionId)
        const sessions = state.sessions.filter(session => session.session_id !== sessionId)
        if (sessions.length === 0) {
          const replacement = await window.hermesDesktop.macSoftAdminChat.createSession()
          localStorage.setItem('macsoft.admin.selected-session', replacement.session_id)
          selectedSessionRef.current = replacement.session_id
          dispatch({ type: 'sessions', selectedSessionId: replacement.session_id, sessions: [replacement] })
          await loadHistory(replacement.session_id)
          return true
        }
        const selectedSessionId = sessions[0].session_id
        localStorage.setItem('macsoft.admin.selected-session', selectedSessionId)
        dispatch({ type: 'sessions', selectedSessionId, sessions })
        await loadHistory(selectedSessionId)
        return true
      } catch {
        dispatch({ type: 'error', message: 'Admin session could not be deleted.' })
        return false
      }
    },
    [loadHistory, state.sessions, state.streaming]
  )

  const submit = useCallback(
    async (value: string) => {
      const message = value.trim()
      const sessionId = selectedSessionRef.current
      if (!enabled || !serverReady || !sessionId || !message || streamIdRef.current || activeRendererAdminStreamId) return false
      const optimistic: MacSoftAdminUiMessage = { content: message, id: `temporary-user-${Date.now()}`, role: 'user' }
      dispatch({ type: 'user-message', message: optimistic })
      try {
        const result = await window.hermesDesktop.macSoftAdminChat.startStream({ message, sessionId })
        activeRendererAdminStreamId = result.streamId
        streamIdRef.current = result.streamId
        dispatch({ type: 'stream-start', streamId: result.streamId })
        return true
      } catch {
        dispatch({ type: 'stream-error', message: 'Admin chat could not start.' })
        return false
      }
    },
    [enabled, serverReady]
  )

  const stop = useCallback(async () => {
    const sessionId = selectedSessionRef.current
    const streamId = streamIdRef.current
    if (!enabled || !sessionId || !streamId || interruptingRef.current) return
    interruptingRef.current = true
    dispatch({ type: 'interrupt-start' })
    try {
      await window.hermesDesktop.macSoftAdminChat.stopStream({ sessionId, streamId })
    } catch {
      interruptingRef.current = false
      dispatch({ type: 'interrupt-error', message: 'Admin chat could not be interrupted.' })
    }
  }, [enabled])

  useEffect(() => {
    if (!enabled || !serverReady) return
    let cancelled = false
    dispatch({ type: 'load-start' })
    void (async () => {
      try {
        let sessions = await window.hermesDesktop.macSoftAdminChat.listSessions()
        if (sessions.length === 0) sessions = [await window.hermesDesktop.macSoftAdminChat.createSession()]
        if (cancelled) return
        const persisted = localStorage.getItem('macsoft.admin.selected-session')
        const selectedSessionId = persisted && sessions.some(session => session.session_id === persisted)
          ? persisted
          : sessions[0].session_id
        localStorage.setItem('macsoft.admin.selected-session', selectedSessionId)
        selectedSessionRef.current = selectedSessionId
        dispatch({ type: 'sessions', selectedSessionId, sessions })
        await loadHistory(selectedSessionId)
      } catch {
        if (!cancelled) dispatch({ type: 'error', message: 'MacSoft Server Admin authentication is unavailable.' })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [enabled, loadHistory, serverReady])

  useEffect(() => {
    if (!enabled) return
    const unsubscribe = window.hermesDesktop.macSoftAdminChat.onStreamEvent(event => {
      if (!streamIdRef.current || event.streamId !== streamIdRef.current) return
      dispatch({ type: 'stream-event', event })
      if (event.event === 'message_done' || event.event === 'error') {
        const sessionId = selectedSessionRef.current
        if (sessionId) void loadHistory(sessionId)
        if (event.event === 'error') {
          const message = typeof event.data.message === 'string' ? event.data.message : 'Admin chat stream failed.'
          dispatch({ type: 'stream-error', message })
        } else if (event.data.ok === false) {
          dispatch({ type: 'stream-error', message: 'Admin chat did not complete successfully.' })
        }
        activeRendererAdminStreamId = null
        streamIdRef.current = null
      }
    })
    return () => unsubscribe()
  }, [enabled, loadHistory])

  return {
    ...state,
    createSession,
    deleteSession,
    selectSession,
    stop,
    submit,
    ...macSoftAdminPromptCapabilities(state, serverReady)
  }
}
