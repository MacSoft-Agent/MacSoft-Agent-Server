import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const electronDir = dirname(fileURLToPath(import.meta.url))

test('keeps the renderer surface narrow and listener cleanup explicit', async () => {
  const preload = await readFile(join(electronDir, 'preload.ts'), 'utf8')

  assert.match(preload, /macSoftAdminChat: \{/)
  assert.match(preload, /ipcRenderer\.invoke\('hermes:macsoft-admin:start-stream'/)
  assert.match(preload, /ipcRenderer\.invoke\('hermes:macsoft-admin:interrupt-stream'/)
  assert.match(preload, /ipcRenderer\.removeListener/)
  assert.doesNotMatch(preload, /adminAccessToken/)
})

test('keeps stream ownership, validation, and SSE event filtering in Electron main', async () => {
  const main = await readFile(join(electronDir, 'main.ts'), 'utf8')

  assert.match(main, /const macSoftAdminStreams = new Map/)
  assert.match(main, /new AbortController\(\)/)
  assert.match(main, /const MACSOFT_ADMIN_MAX_MESSAGE_BYTES = 32_000/)
  assert.match(main, /'message_done'/)
  assert.match(main, /'malformed_stream_event'/)
  assert.match(main, /ipcMain\.handle\('hermes:macsoft-admin:interrupt-stream'/)
  assert.match(main, /active\.webContents !== event\.sender/)
  assert.match(main, /\.interruptAdminChat\(sessionId\)/)
})

test('keeps Admin busy interaction as Stop instead of queueing a second prompt', async () => {
  const composer = await readFile(join(electronDir, '../src/app/chat/composer/index.tsx'), 'utf8')
  const chat = await readFile(join(electronDir, '../src/app/chat/index.tsx'), 'utf8')

  assert.match(composer, /hasComposerPayload && queueWhileBusy \? 'queue' : 'stop'/)
  assert.match(chat, /queueWhileBusy=\{!macSoftCustomerRuntime\}/)
  assert.match(chat, /const cancelPrompt = macSoftCustomerRuntime && adminChat \? adminChat\.stop : onCancel/)
  assert.match(chat, /onCancel=\{cancelPrompt\}/)
  assert.match(
    chat,
    /canSubmitPrompt=\{canSubmitPrompt \|\| \(macSoftCustomerRuntime && Boolean\(adminChat\?\.streaming\)\)\}/
  )
})
