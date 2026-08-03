import assert from 'node:assert/strict'
import test from 'node:test'

import { fetchTrustedMacSoftUpdateResource, type MacSoftUpdateFetch } from './macsoft-update-fetch'

function response(status: number, location?: string): Response {
  return new Response(status === 200 ? 'ok' : null, {
    headers: location ? { location } : undefined,
    status
  })
}

test('follows validated HTTPS redirects without relying on response.url', async () => {
  const requested: string[] = []
  const responses = [
    response(302, '/releases/download/v0.1.2/manifest.json'),
    response(302, 'https://release-assets.githubusercontent.com/manifest.json'),
    response(200)
  ]
  const fetcher: MacSoftUpdateFetch = async (url, init) => {
    requested.push(url)
    assert.equal(init.redirect, 'manual')
    return responses.shift()!
  }

  const result = await fetchTrustedMacSoftUpdateResource(
    'https://github.com/example/releases/latest/download/manifest.json',
    { method: 'GET' },
    fetcher
  )

  assert.equal(result.status, 200)
  assert.deepEqual(requested, [
    'https://github.com/example/releases/latest/download/manifest.json',
    'https://github.com/releases/download/v0.1.2/manifest.json',
    'https://release-assets.githubusercontent.com/manifest.json'
  ])
})

test('rejects a redirect to a non-HTTPS destination', async () => {
  const fetcher: MacSoftUpdateFetch = async () => response(302, 'http://example.test/update.exe')
  await assert.rejects(
    fetchTrustedMacSoftUpdateResource('https://example.test/update.exe', {}, fetcher),
    /trusted HTTPS URLs/
  )
})

test('rejects redirects with credentials or no destination', async () => {
  const credentialFetcher: MacSoftUpdateFetch = async () =>
    response(302, 'https://user:password@example.test/update.exe')
  await assert.rejects(
    fetchTrustedMacSoftUpdateResource('https://example.test/update.exe', {}, credentialFetcher),
    /trusted HTTPS URLs/
  )

  const missingFetcher: MacSoftUpdateFetch = async () => response(302)
  await assert.rejects(
    fetchTrustedMacSoftUpdateResource('https://example.test/update.exe', {}, missingFetcher),
    /did not provide a destination/
  )
})

test('rejects redirect loops after the bounded limit', async () => {
  const fetcher: MacSoftUpdateFetch = async () => response(302, '/again')
  await assert.rejects(
    fetchTrustedMacSoftUpdateResource('https://example.test/update.exe', {}, fetcher),
    /exceeded the redirect limit/
  )
})
