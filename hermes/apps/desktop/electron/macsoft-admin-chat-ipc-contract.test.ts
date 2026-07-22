import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const electronDir = dirname(fileURLToPath(import.meta.url))

describe('MacSoft Admin chat IPC contract', () => {
  it('keeps the renderer surface narrow and listener cleanup explicit', async () => {
    const preload = await readFile(join(electronDir, 'preload.ts'), 'utf8')

    expect(preload).toContain("macSoftAdminChat: {")
    expect(preload).toContain("ipcRenderer.invoke('hermes:macsoft-admin:start-stream'")
    expect(preload).toContain("ipcRenderer.invoke('hermes:macsoft-admin:interrupt-stream'")
    expect(preload).toContain('ipcRenderer.removeListener')
    expect(preload).not.toContain('adminAccessToken')
  })

  it('keeps stream ownership, validation, and SSE event filtering in Electron main', async () => {
    const main = await readFile(join(electronDir, 'main.ts'), 'utf8')

    expect(main).toContain("const macSoftAdminStreams = new Map")
    expect(main).toContain('new AbortController()')
    expect(main).toContain("const MACSOFT_ADMIN_MAX_MESSAGE_BYTES = 32_000")
    expect(main).toContain("'message_done'")
    expect(main).toContain("'malformed_stream_event'")
    expect(main).toContain("ipcMain.handle('hermes:macsoft-admin:interrupt-stream'")
    expect(main).toContain('active.webContents !== event.sender')
    expect(main).toContain('.interruptAdminChat(sessionId)')
  })

  it('keeps Admin busy interaction as Stop instead of queueing a second prompt', async () => {
    const composer = await readFile(join(electronDir, '../src/app/chat/composer/index.tsx'), 'utf8')
    const chat = await readFile(join(electronDir, '../src/app/chat/index.tsx'), 'utf8')

    expect(composer).toContain("hasComposerPayload && queueWhileBusy ? 'queue' : 'stop'")
    expect(chat).toContain('queueWhileBusy={!macSoftCustomerRuntime}')
    expect(chat).toContain('const cancelPrompt = macSoftCustomerRuntime && adminChat ? adminChat.stop : onCancel')
    expect(chat).toContain('onCancel={cancelPrompt}')
    expect(chat).toContain(
      'canSubmitPrompt={canSubmitPrompt || (macSoftCustomerRuntime && Boolean(adminChat?.streaming))}'
    )
  })
})
