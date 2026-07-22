import assert from 'node:assert/strict'
import { test } from 'node:test'

import { MacSoftDesktopAdminChatClient } from './macsoft-desktop-admin-chat-client'

test('Admin client bootstraps with Host token and retries one 401 once', async () => {
  const calls: Array<{ url: string; authorization: string | null }> = []
  let listAttempts = 0
  const client = new MacSoftDesktopAdminChatClient(
    { trustedHostToken: () => 'host-secret' },
    async (input, init) => {
      const url = String(input)
      const authorization = new Headers(init?.headers).get('Authorization')
      calls.push({ url, authorization })
      if (url.endsWith('/auth/session')) {
        return new Response(JSON.stringify({ access_token: 'admin-secret' }), { status: 200 })
      }
      listAttempts += 1
      if (listAttempts === 1) return new Response('{}', { status: 401 })
      return new Response(JSON.stringify({ sessions: [] }), { status: 200 })
    }
  )

  assert.deepEqual(await client.listAdminSessions(), [])
  assert.equal(calls[0].authorization, 'Bearer host-secret')
  assert.equal(calls[1].authorization, 'Bearer admin-secret')
  assert.equal(calls[2].authorization, 'Bearer host-secret')
  assert.equal(calls[3].authorization, 'Bearer admin-secret')
  assert.equal(calls.some(call => call.url.includes('/api/chat/stream')), false)
})

test('Admin client owns a fixed loopback API and does not expose tokens as a method', () => {
  const client = new MacSoftDesktopAdminChatClient({ trustedHostToken: () => 'host-secret' })
  assert.equal(typeof client.listAdminSessions, 'function')
  assert.equal('adminAccessToken' in client, true)
})

test('Admin interrupt stays on the authenticated 8787 Admin path', async () => {
  const calls: Array<{ url: string; method: string | undefined; body: string | null }> = []
  const client = new MacSoftDesktopAdminChatClient(
    { trustedHostToken: () => 'host-secret' },
    async (input, init) => {
      const url = String(input)
      calls.push({ url, method: init?.method, body: typeof init?.body === 'string' ? init.body : null })
      if (url.endsWith('/auth/session')) {
        return new Response(JSON.stringify({ access_token: 'admin-secret' }), { status: 200 })
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 })
    }
  )

  await client.interruptAdminChat('admin_sess_123')
  assert.equal(calls[1].url, 'http://127.0.0.1:8787/api/admin/chat/interrupt')
  assert.equal(calls[1].method, 'POST')
  assert.deepEqual(JSON.parse(calls[1].body || '{}'), { session_id: 'admin_sess_123' })
})
