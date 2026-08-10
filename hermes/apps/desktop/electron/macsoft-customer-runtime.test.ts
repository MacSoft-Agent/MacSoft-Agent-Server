import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('./main.ts', import.meta.url), 'utf8')

test('packaged customer runtime is Host managed before legacy backend discovery', () => {
  const resolver = source.slice(source.indexOf('function resolveHermesBackend'), source.indexOf('async function ensureRuntime'))
  const packagedGate = resolver.indexOf("kind: 'macsoft-host-managed'")
  const legacyDiscovery = resolver.indexOf('HERMES_DESKTOP_HERMES_ROOT')
  assert.ok(packagedGate >= 0)
  assert.ok(legacyDiscovery > packagedGate)
})

test('MacSoft source test mode is explicit and restricted to the Vite development server', () => {
  const packageJson = JSON.parse(fs.readFileSync(new URL('../package.json', import.meta.url), 'utf8'))
  assert.match(source, /const IS_MACSOFT_TEST_RUNTIME = Boolean\(DEV_SERVER\) && process\.env\.MACSOFT_DESKTOP_TEST_MODE === '1'/)
  assert.match(source, /const IS_MACSOFT_CUSTOMER_RUNTIME = IS_PACKAGED \|\| IS_MACSOFT_TEST_RUNTIME/)
  assert.match(source, /event\.returnValue = IS_MACSOFT_CUSTOMER_RUNTIME/)
  assert.match(source, /event\.returnValue = IS_MACSOFT_TEST_RUNTIME/)
  const preload = fs.readFileSync(new URL('./preload.ts', import.meta.url), 'utf8')
  assert.match(preload, /macSoftSourceTestRuntime/)
  assert.equal(packageJson.scripts['dev:macsoft'], 'cross-env MACSOFT_DESKTOP_TEST_MODE=1 npm run dev')
})

test('MacSoft source test runtime restores the original Hermes Messaging navigation', () => {
  const controller = fs.readFileSync(new URL('../src/app/desktop-controller.tsx', import.meta.url), 'utf8')
  const sidebar = fs.readFileSync(new URL('../src/app/chat/sidebar/index.tsx', import.meta.url), 'utf8')
  const systemActions = fs.readFileSync(new URL('../src/store/system-actions.ts', import.meta.url), 'utf8')
  assert.match(controller, /macSoftSourceTestRuntime=\{macSoftSourceTestRuntime\}/)
  assert.match(sidebar, /item\.id === 'messaging'/)
  assert.match(systemActions, /macSoftCustomerRuntime/)
  assert.match(systemActions, /macSoftHost\.serviceAction\('ai_service', 'restart'\)/)
})

test('packaged customer runtime cannot enter the bootstrap downloader', () => {
  const ensure = source.slice(source.indexOf('async function ensureRuntime'), source.indexOf('async function startHermes'))
  const managedGate = ensure.indexOf("backend.kind === 'macsoft-host-managed'")
  const bootstrapRunner = ensure.indexOf('runBootstrap({')
  assert.ok(managedGate >= 0)
  assert.ok(bootstrapRunner > managedGate)
})

test('packaged customer runtime connects to the Host-managed configuration backend', () => {
  const start = source.slice(source.indexOf('async function startHermes'), source.indexOf('function wireCommonWindowHandlers'))
  const packagedGate = start.indexOf('if (IS_MACSOFT_CUSTOMER_RUNTIME)')
  const legacyRuntime = start.indexOf('await waitForUpdateToFinish()')
  assert.ok(packagedGate >= 0)
  assert.ok(legacyRuntime > packagedGate)
  assert.match(start, /configBackendConnection\(\)/)
  assert.match(start, /await waitForHermes\(connection\.baseUrl, connection\.token\)/)
  assert.match(start, /mode: 'macsoft-config-only'/)
  assert.match(start, /wsUrl: null/)
  assert.doesNotMatch(start.slice(packagedGate, legacyRuntime), /spawn\(/)
})

test('packaged renderer connection payload does not expose the Host control token', () => {
  const handler = source.slice(
    source.indexOf("ipcMain.handle('hermes:connection'"),
    source.indexOf("ipcMain.handle('hermes:connection:revalidate'")
  )
  assert.match(handler, /const \{ token: _token, \.\.\.publicConnection \} = connection/)
  assert.match(handler, /token: null/)
  assert.match(handler, /wsUrl: null/)
})

test('renderer keeps Agent gateway boot disabled while restoring provider onboarding', () => {
  const preload = fs.readFileSync(new URL('./preload.ts', import.meta.url), 'utf8')
  const controller = fs.readFileSync(new URL('../src/app/desktop-controller.tsx', import.meta.url), 'utf8')
  const gatewayBoot = fs.readFileSync(new URL('../src/app/gateway/hooks/use-gateway-boot.ts', import.meta.url), 'utf8')
  assert.match(preload, /macSoftCustomerRuntime/)
  assert.match(preload, /macSoftFirstRun/)
  assert.match(controller, /disabled: macSoftCustomerRuntime/)
  assert.match(controller, /SETTINGS_ROUTE\}\?tab=server-autocount/)
  assert.match(controller, /enabled=\{macSoftCustomerRuntime \|\| gatewayState === 'open'\}/)
  assert.match(controller, /!macSoftCustomerRuntime && <GatewayConnectingOverlay/)
  assert.match(controller, /!macSoftCustomerRuntime && <BootFailureOverlay/)
  assert.match(gatewayBoot, /if \(disabled\)/)
})

test('customer Model Settings routes to the original Hermes ConfigSettings', () => {
  const settings = fs.readFileSync(new URL('../src/app/settings/index.tsx', import.meta.url), 'utf8')
  assert.match(settings, /activeView\.startsWith\('config:'\)/)
  assert.match(settings, /<ConfigSettings/)
  assert.doesNotMatch(settings, /MacSoftModelSettings|shouldUseMacSoftModelSettings/)
})

test('packaged product data is initialized before the primary window and first-run navigation is consumed once', () => {
  const ready = source.slice(source.indexOf('app.whenReady().then'), source.indexOf('// Seed Chromium'))
  assert.ok(ready.indexOf('await ensureMacSoftProductData()') >= 0)
  assert.ok(ready.indexOf('createWindow()') > ready.indexOf('await ensureMacSoftProductData()'))
  assert.match(source, /hermes:macsoft-first-run-navigation/)
  assert.match(source, /macSoftFirstRunNavigationPending = false/)
})
