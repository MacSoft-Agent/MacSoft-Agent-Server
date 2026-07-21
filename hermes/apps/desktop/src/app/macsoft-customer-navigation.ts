interface FirstRunNavigationState {
  customerRuntime: boolean
  firstRunPending: boolean
  pathname: string
}

export function shouldOpenFirstRunSettings({
  customerRuntime,
  firstRunPending,
  pathname
}: FirstRunNavigationState): boolean {
  return customerRuntime && firstRunPending && pathname === '/'
}

export function hidesLegacyGatewayUi(customerRuntime: boolean, surfaceId: string): boolean {
  return customerRuntime && surfaceId === 'gateway'
}
