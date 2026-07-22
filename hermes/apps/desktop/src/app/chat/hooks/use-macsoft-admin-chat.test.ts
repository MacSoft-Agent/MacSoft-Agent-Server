import { describe, expect, it } from 'vitest'

import {
  initialMacSoftAdminChatState,
  macSoftAdminPromptCapabilities,
  reduceMacSoftAdminChat
} from './use-macsoft-admin-chat'

const session = {
  created_at: '2026-07-21T00:00:00Z',
  id: 'admin_sess_1',
  session_id: 'admin_sess_1',
  title: 'Admin Chat',
  updated_at: '2026-07-21T00:00:00Z'
}

describe('MacSoft Admin chat reducer', () => {
  it('only enables the composer for a ready server and selected session', () => {
    const loaded = reduceMacSoftAdminChat(initialMacSoftAdminChatState, {
      type: 'sessions',
      selectedSessionId: session.session_id,
      sessions: [session]
    })

    expect(macSoftAdminPromptCapabilities(loaded, false)).toEqual({ canEditPrompt: false, canSubmitPrompt: false })
    expect(macSoftAdminPromptCapabilities(loaded, true)).toEqual({ canEditPrompt: true, canSubmitPrompt: true })
  })

  it('ignores stale stream events and accumulates token deltas', () => {
    const streaming = reduceMacSoftAdminChat(
      reduceMacSoftAdminChat(initialMacSoftAdminChatState, { type: 'stream-start', streamId: 'stream-1' }),
      {
        type: 'stream-event',
        event: { data: { text: 'ignored' }, event: 'token_delta', streamId: 'stream-old' }
      }
    )
    expect(streaming.messages).toHaveLength(0)

    const first = reduceMacSoftAdminChat(streaming, {
      type: 'stream-event',
      event: { data: { text: 'Hello ' }, event: 'token_delta', streamId: 'stream-1' }
    })
    const second = reduceMacSoftAdminChat(first, {
      type: 'stream-event',
      event: { data: { text: 'world' }, event: 'token_delta', streamId: 'stream-1' }
    })

    expect(second.messages).toEqual([
      { content: 'Hello world', id: 'temporary-assistant-stream-1', role: 'assistant', temporary: true }
    ])
  })

  it('clears streaming state on message completion', () => {
    const state = reduceMacSoftAdminChat(
      reduceMacSoftAdminChat(initialMacSoftAdminChatState, { type: 'stream-start', streamId: 'stream-1' }),
      { type: 'stream-event', event: { data: { ok: true }, event: 'message_done', streamId: 'stream-1' } }
    )

    expect(state.streaming).toBe(false)
    expect(state.streamId).toBeNull()
  })

  it('keeps the stream busy while an interrupt is pending and releases it on completion', () => {
    const streaming = reduceMacSoftAdminChat(initialMacSoftAdminChatState, {
      type: 'stream-start',
      streamId: 'stream-1'
    })
    const interrupting = reduceMacSoftAdminChat(streaming, { type: 'interrupt-start' })
    expect(interrupting.streaming).toBe(true)
    expect(interrupting.interrupting).toBe(true)

    const completed = reduceMacSoftAdminChat(interrupting, {
      type: 'stream-event',
      event: { data: { interrupted: true, ok: true }, event: 'message_done', streamId: 'stream-1' }
    })
    expect(completed.streaming).toBe(false)
    expect(completed.interrupting).toBe(false)
    expect(completed.streamId).toBeNull()
  })
})
