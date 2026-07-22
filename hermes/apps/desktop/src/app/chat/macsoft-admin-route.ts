export type MacSoftAdminRouteAction =
  | { type: 'none' }
  | { type: 'new' }
  | { type: 'open'; sessionId: string }

export function resolveMacSoftAdminRouteAction({
  customerRuntime,
  draftTransition,
  openedRoute,
  ready,
  routedSessionId,
  selectedSessionId,
  sessionIds,
  sessionsLoaded
}: {
  customerRuntime: boolean
  draftTransition: boolean
  openedRoute: string | null
  ready: boolean
  routedSessionId: string | null
  selectedSessionId: string | null
  sessionIds: string[]
  sessionsLoaded: boolean
}): MacSoftAdminRouteAction {
  if (draftTransition || !customerRuntime || !ready || !sessionsLoaded || !routedSessionId) {
    return { type: 'none' }
  }

  if (selectedSessionId === routedSessionId || openedRoute === routedSessionId) {
    return { type: 'none' }
  }

  if (!sessionIds.includes(routedSessionId)) {
    return { type: 'new' }
  }

  return { sessionId: routedSessionId, type: 'open' }
}
