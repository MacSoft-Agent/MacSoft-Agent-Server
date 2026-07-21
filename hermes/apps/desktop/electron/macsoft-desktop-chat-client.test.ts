import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  MACSOFT_SERVER_HEALTH_URL,
  MacSoftDesktopChatClient
} from './macsoft-desktop-chat-client'

test('probes the fixed MacSoft Server health endpoint', async () => {
  const calls: string[] = []
  const client = new MacSoftDesktopChatClient(async (url, init) => {
    calls.push(`${url}|${init?.method}`)
    return new Response('{}', { status: 200 })
  })

  assert.deepEqual(await client.getStatus(), { status: 'ready' })
  assert.deepEqual(calls, [`${MACSOFT_SERVER_HEALTH_URL}|GET`])
})

test('normalizes unavailable, timeout, and refused connections without leaking details', async t => {
  await t.test('unhealthy response', async () => {
    const client = new MacSoftDesktopChatClient(async () => new Response('secret stack', { status: 503 }))
    assert.deepEqual(await client.getStatus(), {
      status: 'unavailable',
      message: 'MacSoft Server is unavailable.'
    })
  })

  for (const label of ['timeout', 'connection refused']) {
    await t.test(label, async () => {
      const client = new MacSoftDesktopChatClient(async () => {
        throw new Error(`raw ${label} details and local path`)
      })
      const result = await client.getStatus()

      assert.deepEqual(result, {
        status: 'unavailable',
        message: 'MacSoft Server is unavailable.'
      })
      assert.equal(JSON.stringify(result).includes('raw'), false)
    })
  }
})

test('cannot be redirected by renderer input', async () => {
  let requestedUrl = ''
  const client = new MacSoftDesktopChatClient(async url => {
    requestedUrl = String(url)
    return new Response('{}', { status: 200 })
  })

  await client.getStatus()

  assert.equal(requestedUrl, MACSOFT_SERVER_HEALTH_URL)
})
