import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { HOST_CONTROL_TIMEOUT_MS, MACSOFT_CONFIG_BACKEND_PORT, MacSoftHostClient } from './macsoft-host-client'
import { resolveMacSoftProductPaths } from './macsoft-product'

test('host client uses only loopback and keeps the token in Electron main', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-host-client-'))
  const paths = resolveMacSoftProductPaths({ packaged: true, configuredProgramRoot: path.join(root, 'Program'), configuredDataRoot: path.join(root, 'Data') })
  fs.mkdirSync(path.dirname(paths.hostControlFile), { recursive: true })
  fs.writeFileSync(paths.hostControlFile, JSON.stringify({ host: '127.0.0.1', port: 8766, token: 'x'.repeat(40) }))
  let observedUrl = ''
  let observedAuth = ''
  const client = new MacSoftHostClient(paths, (async (url: string, init: RequestInit) => {
    observedUrl = url
    observedAuth = String((init.headers as Record<string, string>).Authorization)
    return new Response(JSON.stringify({ ok: true, product: 'MacSoft Agent', version: '0.1.0', auto_start: true, services: {} }), { status: 200 })
  }) as typeof fetch)
  const status = await client.status()
  assert.equal(status.version, '0.1.0')
  assert.equal(observedUrl, 'http://127.0.0.1:8766/v1/status')
  assert.equal(observedAuth, `Bearer ${'x'.repeat(40)}`)
})

test('host control timeout covers the Host service health window', () => {
  assert.ok(HOST_CONTROL_TIMEOUT_MS > 60_000)
})

test('pairing code is obtained only through authenticated Host Control', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-host-client-'))
  const paths = resolveMacSoftProductPaths({
    packaged: true,
    configuredProgramRoot: path.join(root, 'Program'),
    configuredDataRoot: path.join(root, 'Data')
  })
  fs.mkdirSync(path.dirname(paths.hostControlFile), { recursive: true })
  fs.writeFileSync(paths.hostControlFile, JSON.stringify({ host: '127.0.0.1', port: 8766, token: 'p'.repeat(40) }))
  let observedUrl = ''
  let observedAuth = ''
  const client = new MacSoftHostClient(paths, (async (url: string, init: RequestInit) => {
    observedUrl = url
    observedAuth = String((init.headers as Record<string, string>).Authorization)
    return new Response(JSON.stringify({ ok: true, pairing_code: 'PAIR-123456' }), { status: 200 })
  }) as typeof fetch)

  assert.equal(await client.pairingCode(), 'PAIR-123456')
  assert.equal(observedUrl, 'http://127.0.0.1:8766/v1/pairing-code')
  assert.equal(observedAuth, `Bearer ${'p'.repeat(40)}`)
  fs.rmSync(root, { force: true, recursive: true })
})

test('configuration backend reuses the loopback Host-control token', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-host-client-'))
  const paths = resolveMacSoftProductPaths({
    packaged: true,
    configuredProgramRoot: path.join(root, 'Program'),
    configuredDataRoot: path.join(root, 'Data')
  })
  fs.mkdirSync(path.dirname(paths.hostControlFile), { recursive: true })
  fs.writeFileSync(paths.hostControlFile, JSON.stringify({ host: '127.0.0.1', port: 8766, token: 'z'.repeat(40) }))

  const connection = new MacSoftHostClient(paths).configBackendConnection()

  assert.equal(connection.baseUrl, `http://127.0.0.1:${MACSOFT_CONFIG_BACKEND_PORT}`)
  assert.equal(connection.token, 'z'.repeat(40))
  fs.rmSync(root, { force: true, recursive: true })
})

test('missing Host control state is reported as stopped without exposing ENOENT', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-host-client-'))
  const paths = resolveMacSoftProductPaths({
    packaged: true,
    configuredProgramRoot: path.join(root, 'Program'),
    configuredDataRoot: path.join(root, 'Data')
  })
  let fetchCalls = 0
  const client = new MacSoftHostClient(paths, (async () => {
    fetchCalls += 1
    throw new Error('fetch should not run')
  }) as typeof fetch)

  const status = await client.status()

  assert.equal(fetchCalls, 0)
  assert.equal(status.auto_start, false)
  assert.equal(status.services.ai_service.status, 'stopped')
  assert.equal(status.services.server.status, 'stopped')
  await assert.rejects(client.serviceAction('server', 'start'), /Host is not registered or running yet/)
  fs.rmSync(root, { force: true, recursive: true })
})

test('malformed Host control state is reported without exposing parser details', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-host-client-'))
  const paths = resolveMacSoftProductPaths({
    packaged: true,
    configuredProgramRoot: path.join(root, 'Program'),
    configuredDataRoot: path.join(root, 'Data')
  })
  fs.mkdirSync(path.dirname(paths.hostControlFile), { recursive: true })
  fs.writeFileSync(paths.hostControlFile, '{not-json')
  const client = new MacSoftHostClient(paths)
  await assert.rejects(client.status(), /^Error: MacSoft Agent Host control configuration is invalid\.$/)
  fs.rmSync(root, { force: true, recursive: true })
})

test('stale Host control state maps transport failures to a readable error', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-host-client-'))
  const paths = resolveMacSoftProductPaths({
    packaged: true,
    configuredProgramRoot: path.join(root, 'Program'),
    configuredDataRoot: path.join(root, 'Data')
  })
  fs.mkdirSync(path.dirname(paths.hostControlFile), { recursive: true })
  fs.writeFileSync(paths.hostControlFile, JSON.stringify({ host: '127.0.0.1', port: 8766, token: 'x'.repeat(40) }))
  const client = new MacSoftHostClient(paths, (async () => {
    throw new TypeError('fetch failed')
  }) as typeof fetch)
  await assert.rejects(client.status(), /^Error: MacSoft Agent Host is unavailable\.$/)
  fs.rmSync(root, { force: true, recursive: true })
})
