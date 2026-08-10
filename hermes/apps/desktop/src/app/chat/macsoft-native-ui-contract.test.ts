import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const chatSource = readFileSync(join(process.cwd(), 'src/app/chat/index.tsx'), 'utf8')
const controllerSource = readFileSync(join(process.cwd(), 'src/app/desktop-controller.tsx'), 'utf8')
const sidebarSource = readFileSync(join(process.cwd(), 'src/app/chat/sidebar/index.tsx'), 'utf8')

describe('MacSoft Admin chat UI contract', () => {
  it('keeps the native Thread and composer instead of rendering a parallel Admin surface', () => {
    expect(chatSource).toContain('<Thread')
    expect(chatSource).toContain('<ChatBar')
    expect(chatSource).not.toContain('MacSoftAdminChatSurface')
    expect(chatSource).not.toContain('Admin chat session')
  })

  it('uses the existing sidebar and exposes all native navigation in the MacSoft customer runtime', () => {
    expect(controllerSource).toContain('macSoftCustomerRuntime={macSoftCustomerRuntime}')
    expect(sidebarSource).toContain('SIDEBAR_NAV.map(item =>')
    expect(sidebarSource).not.toContain('SIDEBAR_NAV.filter(')
    expect(controllerSource).toContain("macSoftCustomerRuntime && item.action === 'new-session'")
    expect(controllerSource).toContain('onNavigate={handleSidebarNavigate}')
  })

  it('does not restore the remembered session on MacSoft startup', () => {
    expect(controllerSource).toContain('!macSoftCustomerRuntime && last && location.pathname === NEW_CHAT_ROUTE')
  })
})
