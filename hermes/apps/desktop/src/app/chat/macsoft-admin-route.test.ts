import { describe, expect, it } from 'vitest'

import { resolveMacSoftAdminRouteAction } from './macsoft-admin-route'

const base = {
  customerRuntime: true,
  draftTransition: false,
  openedRoute: null,
  ready: true,
  routedSessionId: 'admin-1',
  selectedSessionId: null,
  sessionIds: ['admin-1'],
  sessionsLoaded: true
}

describe('MacSoft Admin route bridge', () => {
  it('waits for a delayed session index before opening the restored route', () => {
    expect(resolveMacSoftAdminRouteAction({ ...base, sessionIds: [], sessionsLoaded: false })).toEqual({
      type: 'none'
    })
    expect(resolveMacSoftAdminRouteAction(base)).toEqual({ sessionId: 'admin-1', type: 'open' })
  })

  it('does not reopen an active route and rejects a missing persisted route', () => {
    expect(resolveMacSoftAdminRouteAction({ ...base, selectedSessionId: 'admin-1' })).toEqual({ type: 'none' })
    expect(resolveMacSoftAdminRouteAction({ ...base, sessionIds: [] })).toEqual({ type: 'new' })
  })

  it('does not reopen the previous session while a new draft transition is settling', () => {
    expect(
      resolveMacSoftAdminRouteAction({
        ...base,
        draftTransition: true,
        routedSessionId: 'admin-1',
        selectedSessionId: 'admin-1'
      })
    ).toEqual({ type: 'none' })
  })
})
