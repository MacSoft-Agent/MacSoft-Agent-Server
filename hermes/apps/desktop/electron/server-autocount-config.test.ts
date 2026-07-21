import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  detectNetworkAddresses,
  patchYamlScalar,
  readYamlScalar,
  ServerAutoCountConfigService
} from './server-autocount-config'

function response(status: number, body: unknown) {
  return {
    json: async () => body,
    ok: status >= 200 && status < 300,
    status
  }
}

function fixture(root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-settings-'))) {
  const serverPath = path.join(root, 'server', 'macsoft-server.yaml')
  const runtimePath = path.join(root, 'runtime', 'config.yaml')
  const pluginPath = path.join(root, 'runtime', 'plugins', 'macsoft-autocount', 'config.json')
  fs.mkdirSync(path.dirname(serverPath), { recursive: true })
  fs.mkdirSync(path.dirname(pluginPath), { recursive: true })
  fs.writeFileSync(
    serverPath,
    [
      'server:',
      '  host: 0.0.0.0 # keep this comment',
      '  port: 8787',
      'hermes:',
      '  api_base_url: "http://127.0.0.1:8642"',
      '  api_key: "server-secret"',
      'unrelated:',
      '  keep: true',
      ''
    ].join('\r\n')
  )
  fs.writeFileSync(
    runtimePath,
    [
      'model:',
      '  provider: openai-codex # keep provider comment',
      '  default: gpt-5.4 # keep model comment',
      'platforms:',
      '  api_server:',
      '    enabled: true',
      '    extra:',
      '      host: 127.0.0.1',
      '      port: 8642 # runtime port',
      '      key: "runtime-secret"',
      'authentication:',
      '  source: auth.json',
      'unknown_root:',
      '  preserve: true',
      ''
    ].join('\n')
  )
  fs.writeFileSync(
    pluginPath,
    `\ufeff${JSON.stringify(
      {
        baseUrl: 'https://api.autocount.cloud',
        apiKey: 'existing-secret',
        connectorId: 'main-connector',
        companyId: 'testing',
        requestTimeoutSeconds: 30,
        unrelated: { keep: true }
      },
      null,
      2
    )}\n`
  )

  return { pluginPath, root, runtimePath, serverPath }
}

const physicalNetworks = () =>
  ({
    'vEthernet (WSL)': [
      {
        address: '172.29.0.1',
        cidr: '172.29.0.1/20',
        family: 'IPv4',
        internal: false,
        mac: '00:00:00:00:00:01',
        netmask: '255.255.240.0'
      }
    ],
    Ethernet: [
      {
        address: '192.168.1.42',
        cidr: '192.168.1.42/24',
        family: 'IPv4',
        internal: false,
        mac: '00:00:00:00:00:02',
        netmask: '255.255.255.0'
      }
    ],
    Loopback: [
      {
        address: '127.0.0.1',
        cidr: '127.0.0.1/8',
        family: 'IPv4',
        internal: true,
        mac: '00:00:00:00:00:00',
        netmask: '255.0.0.0'
      }
    ],
    'Wi-Fi': [
      {
        address: '169.254.10.3',
        cidr: '169.254.10.3/16',
        family: 'IPv4',
        internal: false,
        mac: '00:00:00:00:00:03',
        netmask: '255.255.0.0'
      }
    ]
  }) as ReturnType<typeof os.networkInterfaces>

test('YAML scalar helpers preserve comments and line endings', () => {
  const source = 'server:\r\n  port: 8787 # client-facing\r\nother: true\r\n'
  const patched = patchYamlScalar(source, ['server', 'port'], 8888)

  assert.equal(readYamlScalar(patched, ['server', 'port']), '8888')
  assert.match(patched, /port: 8888 # client-facing\r\n/)
  assert.match(patched, /other: true\r\n$/)
})

test('network detection rejects loopback and link-local and prefers physical LAN', () => {
  const result = detectNetworkAddresses(physicalNetworks())

  assert.equal(result.recommendedAddress, '192.168.1.42')
  assert.deepEqual(
    result.addresses.map(item => [item.address, item.kind, item.recommended]),
    [
      ['192.168.1.42', 'ethernet', true],
      ['172.29.0.1', 'virtual', false]
    ]
  )
})

test('loadSettings returns API key presence only and readable status', async t => {
  const files = fixture()
  t.after(() => fs.rmSync(files.root, { force: true, recursive: true }))

  const service = new ServerAutoCountConfigService({
    fetchImpl: async () => response(200, { ok: true }),
    networkInterfaces: physicalNetworks,
    projectRoot: files.root
  })

  const loaded = await service.loadSettings()

  assert.equal(loaded.autoCount.apiKeyConfigured, true)
  assert.equal(JSON.stringify(loaded).includes('existing-secret'), false)
  assert.equal(loaded.recommendedAddress, '192.168.1.42')
  assert.equal(loaded.clientUrl, 'http://192.168.1.42:8787')
  assert.equal(loaded.server.status.title, 'MacSoft Server running')
  assert.equal(loaded.aiService.status.title, 'AI Service running')
})

test('loadModelSettings reads the configured provider and model only', async t => {
  const files = fixture()
  t.after(() => fs.rmSync(files.root, { force: true, recursive: true }))
  const service = new ServerAutoCountConfigService({ projectRoot: files.root })

  assert.deepEqual(await service.loadModelSettings(), {
    model: 'gpt-5.4',
    provider: 'openai-codex'
  })
})

test('saveModelSettings patches only model scalars and preserves comments, secrets, and unknown fields', async t => {
  const files = fixture()
  t.after(() => fs.rmSync(files.root, { force: true, recursive: true }))
  const before = fs.readFileSync(files.runtimePath, 'utf8')
  const service = new ServerAutoCountConfigService({
    now: () => new Date('2026-07-15T02:30:00.000Z'),
    projectRoot: files.root
  })

  const result = await service.saveModelSettings({ model: 'claude-sonnet-4', provider: 'openrouter' })
  const after = fs.readFileSync(files.runtimePath, 'utf8')
  const expected = before
    .replace('provider: openai-codex', 'provider: "openrouter"')
    .replace('default: gpt-5.4', 'default: "claude-sonnet-4"')

  assert.equal(after, expected)
  assert.equal(readYamlScalar(after, ['model', 'provider']), 'openrouter')
  assert.equal(readYamlScalar(after, ['model', 'default']), 'claude-sonnet-4')
  assert.match(after, /keep provider comment/)
  assert.match(after, /keep model comment/)
  assert.match(after, /key: "runtime-secret"/)
  assert.match(after, /source: auth\.json/)
  assert.match(after, /unknown_root:\n  preserve: true/)
  assert.equal(result.changedFiles.length, 1)
  assert.equal(result.backups.length, 1)
  assert.equal(fs.readFileSync(result.backups[0], 'utf8'), before)
  assert.deepEqual(result.settings, { model: 'claude-sonnet-4', provider: 'openrouter' })
})

test('saveModelSettings makes no backup when the provider and model are unchanged', async t => {
  const files = fixture()
  t.after(() => fs.rmSync(files.root, { force: true, recursive: true }))
  const service = new ServerAutoCountConfigService({ projectRoot: files.root })

  const result = await service.saveModelSettings({ model: 'gpt-5.4', provider: 'openai-codex' })

  assert.deepEqual(result.changedFiles, [])
  assert.deepEqual(result.backups, [])
})

test('loadSettings initializes a legitimate missing first-run configuration and retries once', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-settings-empty-'))
  t.after(() => fs.rmSync(root, { force: true, recursive: true }))
  let initializeCalls = 0

  const service = new ServerAutoCountConfigService({
    ensureProductData: async () => {
      initializeCalls += 1
      fixture(root)
    },
    fetchImpl: async () => response(200, { ok: true }),
    networkInterfaces: physicalNetworks,
    projectRoot: root
  })

  const loaded = await service.loadSettings()

  assert.equal(initializeCalls, 1)
  assert.equal(loaded.server.port, 8787)
  assert.equal(loaded.aiService.port, 8642)
})

test('loadSettings reports a missing configuration without exposing raw ENOENT', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'macsoft-settings-empty-'))
  t.after(() => fs.rmSync(root, { force: true, recursive: true }))
  const service = new ServerAutoCountConfigService({
    fetchImpl: async () => response(200, { ok: true }),
    networkInterfaces: physicalNetworks,
    projectRoot: root
  })

  await assert.rejects(
    service.loadSettings(),
    error => error instanceof Error && /configuration is incomplete/.test(error.message) && !/ENOENT/.test(error.message)
  )
})

test('loadSettings preserves and reports malformed existing JSON without initializing over it', async t => {
  const files = fixture()
  t.after(() => fs.rmSync(files.root, { force: true, recursive: true }))
  const malformed = '{ "baseUrl": '
  fs.writeFileSync(files.pluginPath, malformed)
  let initializeCalls = 0
  const service = new ServerAutoCountConfigService({
    ensureProductData: async () => {
      initializeCalls += 1
    },
    fetchImpl: async () => response(200, { ok: true }),
    networkInterfaces: physicalNetworks,
    projectRoot: files.root
  })

  await assert.rejects(service.loadSettings(), /contains invalid JSON.*existing file was preserved/)
  assert.equal(initializeCalls, 0)
  assert.equal(fs.readFileSync(files.pluginPath, 'utf8'), malformed)
})

test('loadSettings preserves a customized existing server configuration', async t => {
  const files = fixture()
  t.after(() => fs.rmSync(files.root, { force: true, recursive: true }))
  const customized = fs.readFileSync(files.serverPath, 'utf8').replace('port: 8787', 'port: 9988')
  fs.writeFileSync(files.serverPath, customized)
  const service = new ServerAutoCountConfigService({
    fetchImpl: async () => response(200, { ok: true }),
    networkInterfaces: physicalNetworks,
    projectRoot: files.root
  })

  const loaded = await service.loadSettings()

  assert.equal(loaded.server.port, 9988)
  assert.equal(fs.readFileSync(files.serverPath, 'utf8'), customized)
})

test('saveSettings creates backups, preserves unrelated data, and retains an unchanged API key', async t => {
  const files = fixture()
  t.after(() => fs.rmSync(files.root, { force: true, recursive: true }))

  const service = new ServerAutoCountConfigService({
    fetchImpl: async () => response(200, { ok: true }),
    networkInterfaces: physicalNetworks,
    now: () => new Date('2026-07-13T08:09:10.123Z'),
    projectRoot: files.root
  })

  const result = await service.saveSettings({
    aiServicePort: 8742,
    aiServiceUrl: 'http://127.0.0.1:8642',
    cloudUrl: 'https://api.autocount.cloud',
    companyId: 'production',
    connectorId: 'office-connector',
    serverPort: 8888
  })

  const server = fs.readFileSync(files.serverPath, 'utf8')
  const runtime = fs.readFileSync(files.runtimePath, 'utf8')
  const plugin = JSON.parse(fs.readFileSync(files.pluginPath, 'utf8').replace(/^\ufeff/, ''))

  assert.equal(readYamlScalar(server, ['server', 'port']), '8888')
  assert.equal(readYamlScalar(server, ['hermes', 'api_base_url']), 'http://127.0.0.1:8742')
  assert.equal(readYamlScalar(runtime, ['platforms', 'api_server', 'extra', 'port']), '8742')
  assert.match(server, /keep this comment/)
  assert.match(server, /unrelated:/)
  assert.equal(plugin.apiKey, 'existing-secret')
  assert.deepEqual(plugin.unrelated, { keep: true })
  assert.equal(plugin.connectorId, 'office-connector')
  assert.equal(plugin.companyId, 'production')
  assert.equal(result.backups.length, 3)
  assert.deepEqual(result.servicesToRestart, ['MacSoft Server', 'AI Service'])
  result.backups.forEach(backup => assert.equal(fs.existsSync(backup), true))
})

test('saveSettings rejects accidental Bearer prefixes before writing', async t => {
  const files = fixture()
  t.after(() => fs.rmSync(files.root, { force: true, recursive: true }))
  const before = fs.readFileSync(files.pluginPath, 'utf8')

  const service = new ServerAutoCountConfigService({
    fetchImpl: async () => response(200, { ok: true }),
    networkInterfaces: physicalNetworks,
    projectRoot: files.root
  })

  await assert.rejects(
    service.saveSettings({
      aiServicePort: 8642,
      aiServiceUrl: 'http://127.0.0.1:8642',
      apiKey: 'Bearer wrong-shape',
      cloudUrl: 'https://api.autocount.cloud',
      companyId: 'testing',
      connectorId: 'main-connector',
      serverPort: 8787
    }),
    /Remove the "Bearer " prefix/
  )
  assert.equal(fs.readFileSync(files.pluginPath, 'utf8'), before)
})

test('AutoCount test uses the existing key without returning it and formats connector details', async t => {
  const files = fixture()
  t.after(() => fs.rmSync(files.root, { force: true, recursive: true }))
  let authorization = ''

  const service = new ServerAutoCountConfigService({
    fetchImpl: async (_url, init) => {
      authorization = String((init?.headers as Record<string, string>).Authorization)

      return response(200, {
        online: true,
        companyName: 'Testing Company',
        databaseName: 'AED_Testing',
        sqlServer: '(local)\\A2006',
        connectorVersion: '2.3.4',
        updateRequired: false,
        writeAuthorized: true
      })
    },
    networkInterfaces: physicalNetworks,
    projectRoot: files.root
  })

  const result = await service.testAutoCount({
    cloudUrl: 'https://api.autocount.cloud',
    companyId: 'testing',
    connectorId: 'main-connector'
  })

  assert.equal(authorization, 'Bearer existing-secret')
  assert.equal(result.ok, true)
  assert.equal(result.title, 'AutoCount connected')
  assert.equal(result.fields?.find(field => field.label === 'Database')?.value, 'AED_Testing')
  assert.equal(JSON.stringify(result).includes('existing-secret'), false)
})

test('AutoCount authentication errors are sanitized and actionable', async t => {
  const files = fixture()
  t.after(() => fs.rmSync(files.root, { force: true, recursive: true }))

  const service = new ServerAutoCountConfigService({
    fetchImpl: async () => response(401, { token: 'must-not-surface', stack: 'must-not-surface' }),
    networkInterfaces: physicalNetworks,
    projectRoot: files.root
  })

  const result = await service.testAutoCount({
    cloudUrl: 'https://api.autocount.cloud',
    companyId: 'testing',
    connectorId: 'main-connector'
  })

  assert.equal(result.ok, false)
  assert.equal(result.title, 'AutoCount authentication failed')
  assert.equal(result.details, 'HTTP 401')
  assert.equal(JSON.stringify(result).includes('must-not-surface'), false)
})
