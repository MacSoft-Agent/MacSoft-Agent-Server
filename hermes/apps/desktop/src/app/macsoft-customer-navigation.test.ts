import { expect, test } from 'vitest'

import { hidesLegacyGatewayUi, shouldOpenFirstRunSettings } from './macsoft-customer-navigation'

test('customer settings redirect is limited to one pending first-run visit', () => {
  expect(shouldOpenFirstRunSettings({ customerRuntime: true, firstRunPending: true, pathname: '/' })).toBe(true)
  expect(shouldOpenFirstRunSettings({ customerRuntime: true, firstRunPending: false, pathname: '/' })).toBe(false)
})

test('development and non-root navigation never force customer settings', () => {
  expect(shouldOpenFirstRunSettings({ customerRuntime: false, firstRunPending: true, pathname: '/' })).toBe(false)
  expect(shouldOpenFirstRunSettings({ customerRuntime: true, firstRunPending: true, pathname: '/settings' })).toBe(false)
})

test('packaged customer mode hides only the legacy Gateway surface', () => {
  expect(hidesLegacyGatewayUi(true, 'gateway')).toBe(true)
  expect(hidesLegacyGatewayUi(true, 'server-autocount')).toBe(false)
  expect(hidesLegacyGatewayUi(false, 'gateway')).toBe(false)
})
