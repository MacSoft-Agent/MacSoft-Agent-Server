export function shouldOpenFirstRunSettings({ customerRuntime, firstRunPending, pathname }) {
    return customerRuntime && firstRunPending && pathname === '/';
}
export function hidesLegacyGatewayUi(customerRuntime, surfaceId) {
    return customerRuntime && surfaceId === 'gateway';
}
