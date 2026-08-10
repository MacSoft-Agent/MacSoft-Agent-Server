import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { MacSoftAdminMessage, MacSoftAdminSession, MacSoftAdminStreamEvent } from '@/global'
import { chatMessageText } from '@/lib/chat-messages'

import {
  initialMacSoftAdminChatState,
  macSoftAdminPromptCapabilities,
  messageFromServer,
  reconcileAdminMessages,
  sessionFromServer,
  useMacSoftAdminChat
} from './use-macsoft-admin-chat'

const session = (id: string): MacSoftAdminSession => ({
  created_at: '2026-07-21T00:00:00Z',
  id,
  session_id: id,
  session_type: 'chat',
  title: `Admin ${id}`,
  updated_at: '2026-07-21T00:00:00Z'
})

const persistedMessage = (
  id: string,
  role: 'assistant' | 'user',
  content: string,
  sessionId = 'admin-1'
): MacSoftAdminMessage => ({
  content,
  created_at: '2026-07-21T00:00:01Z',
  id,
  message_id: id,
  model: null,
  role,
  session_id: sessionId,
  status: 'complete'
})

function deferred<T>() {
  let resolve!: (value: T) => void

  const promise = new Promise<T>(next => {
    resolve = next
  })

  return { promise, resolve }
}

function installApi(overrides: Record<string, unknown> = {}) {
  let listener: ((event: MacSoftAdminStreamEvent) => void) | null = null
  let streamCounter = 0

  const api = {
    createSession: vi.fn(async () => session('admin-new')),
    deleteSession: vi.fn(async () => undefined),
    getMessages: vi.fn(async () => [] as MacSoftAdminMessage[]),
    listSessions: vi.fn(async () => [session('admin-1')]),
    onStreamEvent: vi.fn((next: (event: MacSoftAdminStreamEvent) => void) => {
      listener = next

      return vi.fn()
    }),
    startStream: vi.fn(async () => ({ streamId: `stream-${++streamCounter}` })),
    stopStream: vi.fn(async () => ({ ok: true })),
    ...overrides
  }

  Object.defineProperty(window, 'hermesDesktop', {
    configurable: true,
    value: { macSoftAdminChat: api }
  })

  return {
    api,
    emit(event: MacSoftAdminStreamEvent) {
      listener?.(event)
    }
  }
}

describe('MacSoft Admin chat transport', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('keeps the original new-session composer editable before creating a session', () => {
    expect(macSoftAdminPromptCapabilities(initialMacSoftAdminChatState, true)).toEqual({
      canEditPrompt: true,
      canSubmitPrompt: true
    })
  })

  it('maps 8787 sessions and messages into native Desktop models', () => {
    expect(sessionFromServer(session('admin-1'))).toMatchObject({
      id: 'admin-1',
      source: 'desktop',
      title: 'Admin admin-1'
    })
    expect(messageFromServer(persistedMessage('message-1', 'assistant', 'Persisted reply'))).toMatchObject({
      id: 'message-1',
      parts: [{ text: 'Persisted reply', type: 'text' }],
      role: 'assistant'
    })
  })

  it('does not let an older persisted snapshot erase a newer local transcript', () => {
    const local = [
      messageFromServer(persistedMessage('u1', 'user', 'one'))!,
      messageFromServer(persistedMessage('a1', 'assistant', 'answer one'))!,
      messageFromServer(persistedMessage('u2', 'user', 'two'))!,
      messageFromServer(persistedMessage('a2', 'assistant', 'answer two'))!
    ]

    const stale = local.slice(0, 2)

    const incomplete = [
      messageFromServer(persistedMessage('u1', 'user', 'one'))!,
      messageFromServer(persistedMessage('a1', 'assistant', ''))!,
      ...local.slice(2)
    ]

    expect(reconcileAdminMessages(local, stale)).toBe(local)
    expect(reconcileAdminMessages(local, incomplete)).toBe(local)
  })

  it('opens a restored session after a delayed session index finishes loading', async () => {
    const sessionIndex = deferred<MacSoftAdminSession[]>()

    const { api } = installApi({
      getMessages: vi.fn(async () => [persistedMessage('a1', 'assistant', 'restored')]),
      listSessions: vi.fn(() => sessionIndex.promise)
    })

    const { result } = renderHook(() => useMacSoftAdminChat(true, true))

    expect(result.current.sessionsLoaded).toBe(false)
    await act(async () => sessionIndex.resolve([session('admin-1')]))
    await waitFor(() => expect(result.current.sessionsLoaded).toBe(true))

    await act(async () => {
      await result.current.selectSession('admin-1')
    })

    expect(api.getMessages).toHaveBeenCalledWith('admin-1')
    expect(result.current.selectedSessionId).toBe('admin-1')
    expect(chatMessageText(result.current.messages[0])).toBe('restored')
  })

  it('keeps the first new-session prompt while routing and streaming the response', async () => {
    const { emit } = installApi({ listSessions: vi.fn(async () => []) })
    const { result } = renderHook(() => useMacSoftAdminChat(true, true))

    await waitFor(() => expect(result.current.sessionsLoaded).toBe(true))
    await act(async () => {
      await result.current.submit('first prompt')
    })

    expect(result.current.selectedSessionId).toBe('admin-new')
    expect(result.current.messages.map(chatMessageText)).toEqual(['first prompt', ''])
    expect(result.current.messages[1].pending).toBe(true)

    await act(async () => {
      await result.current.selectSession('admin-new')
    })
    expect(result.current.messages.map(chatMessageText)).toEqual(['first prompt', ''])

    act(() => {
      emit({ data: { message_id: 'assistant-1' }, event: 'message_start', streamId: 'stream-1' })
      emit({ data: { text: 'Hello ' }, event: 'token_delta', streamId: 'stream-1' })
      emit({ data: { text: 'world' }, event: 'token_delta', streamId: 'stream-1' })
    })

    expect(result.current.messages.map(chatMessageText)).toEqual(['first prompt', 'Hello world'])
  })

  it('atomically releases pending, busy, activity and interrupt state on message_done', async () => {
    const { api, emit } = installApi({ listSessions: vi.fn(async () => []) })
    const { result } = renderHook(() => useMacSoftAdminChat(true, true))

    await waitFor(() => expect(result.current.sessionsLoaded).toBe(true))
    await act(async () => {
      await result.current.submit('stop test')
    })
    act(() => emit({ data: { title: 'Thinking' }, event: 'activity', streamId: 'stream-1' }))
    expect(result.current.activity?.title).toBe('Thinking')

    await act(async () => result.current.stop())
    expect(api.stopStream).toHaveBeenCalledWith({ sessionId: 'admin-new', streamId: 'stream-1' })
    expect(result.current.interrupting).toBe(true)

    act(() => emit({ data: { interrupted: true, ok: true }, event: 'message_done', streamId: 'stream-1' }))

    expect(result.current.streaming).toBe(false)
    expect(result.current.interrupting).toBe(false)
    expect(result.current.activity).toBeNull()
    expect(result.current.streamId).toBeNull()
    expect(result.current.messages.at(-1)?.pending).toBe(false)
  })

  it('preserves the first turn when a second prompt starts and stale history arrives', async () => {
    const history = vi.fn(async () => [
      persistedMessage('user-1', 'user', 'first'),
      persistedMessage('assistant-1', 'assistant', 'answer one')
    ])

    const { emit } = installApi({ getMessages: history, listSessions: vi.fn(async () => []) })
    const { result } = renderHook(() => useMacSoftAdminChat(true, true))

    await waitFor(() => expect(result.current.sessionsLoaded).toBe(true))
    await act(async () => result.current.submit('first'))
    act(() => {
      emit({ data: { message_id: 'assistant-1' }, event: 'message_start', streamId: 'stream-1' })
      emit({ data: { text: 'answer one' }, event: 'token_delta', streamId: 'stream-1' })
      emit({ data: { ok: true }, event: 'message_done', streamId: 'stream-1' })
    })

    await act(async () => result.current.submit('second'))
    expect(result.current.messages.map(chatMessageText)).toEqual(['first', 'answer one', 'second', ''])

    act(() => {
      emit({ data: { message_id: 'assistant-2' }, event: 'message_start', streamId: 'stream-2' })
      emit({ data: { text: 'answer two' }, event: 'token_delta', streamId: 'stream-2' })
    })
    expect(result.current.messages.map(chatMessageText)).toEqual(['first', 'answer one', 'second', 'answer two'])
  })

  it('keeps active runs and messages isolated between sessions', async () => {
    const { emit } = installApi({
      getMessages: vi.fn(async () => []),
      listSessions: vi.fn(async () => [session('admin-1'), session('admin-2')])
    })

    const { result } = renderHook(() => useMacSoftAdminChat(true, true))

    await waitFor(() => expect(result.current.sessionsLoaded).toBe(true))
    await act(async () => result.current.selectSession('admin-1'))
    await act(async () => result.current.submit('session one'))
    await act(async () => result.current.selectSession('admin-2'))
    expect(result.current.messages).toEqual([])

    act(() => emit({ data: { text: 'private result' }, event: 'token_delta', streamId: 'stream-1' }))
    expect(result.current.messages).toEqual([])

    await act(async () => result.current.selectSession('admin-1'))
    expect(result.current.messages.map(chatMessageText)).toEqual(['session one', 'private result'])
    expect(result.current.streaming).toBe(true)
  })
})
