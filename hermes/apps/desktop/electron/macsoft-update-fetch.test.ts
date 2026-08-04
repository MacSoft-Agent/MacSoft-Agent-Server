import assert from 'node:assert/strict'
import test from 'node:test'

import { fetchTrustedMacSoftUpdateResource, type MacSoftUpdateFetch } from './macsoft-update-fetch'

test('delegates redirect following to Electron without relying on response.url', async () => {
  const controller = new AbortController()
  let requested = ''
  const fetcher: MacSoftUpdateFetch = async (url, init) => {
    requested = url
    assert.equal(init.redirect, 'follow')
    assert.equal(init.signal, controller.signal)
    return new Response('ok', { status: 200 })
  }

  const result = await fetchTrustedMacSoftUpdateResource(
    'https://github.com/example/releases/latest/download/manifest.json',
    { method: 'GET', redirect: 'manual', signal: controller.signal },
    fetcher
  )

  assert.equal(result.status, 200)
  assert.equal(requested, 'https://github.com/example/releases/latest/download/manifest.json')
})

test('rejects a configured non-HTTPS URL before fetching', async () => {
  let called = false
  const fetcher: MacSoftUpdateFetch = async () => {
    called = true
    return new Response('unexpected')
  }
  await assert.rejects(
    fetchTrustedMacSoftUpdateResource('http://example.test/update.exe', {}, fetcher),
    /trusted HTTPS URLs/
  )
  assert.equal(called, false)
})

test('rejects credentials in the configured URL before fetching', async () => {
  let called = false
  const fetcher: MacSoftUpdateFetch = async () => {
    called = true
    return new Response('unexpected')
  }
  await assert.rejects(
    fetchTrustedMacSoftUpdateResource('https://user:password@example.test/update.exe', {}, fetcher),
    /trusted HTTPS URLs/
  )
  assert.equal(called, false)
})
