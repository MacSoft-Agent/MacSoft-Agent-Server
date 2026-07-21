import assert from 'node:assert/strict'
import test from 'node:test'

import { hidesLegacyGatewayUi, shouldOpenFirstRunSettings } from './macsoft-customer-navigation'

test('customer settings redirect is limited to one pending first-run visit', () => {
  assert.equal(
    shouldOpenFirstRunSettings({ customerRuntime: true, firstRunPending: true, pathname: '/' }),
    true
  )
  assert.equal(
    shouldOpenFirstRunSettings({ customerRuntime: true, firstRunPending: false, pathname: '/' }),
    false
  )
})

test('development and non-root navigation never force customer settings', () => {
  assert.equal(
    shouldOpenFirstRunSettings({ customerRuntime: false, firstRunPending: true, pathname: '/' }),
    false
  )
  assert.equal(
    shouldOpenFirstRunSettings({ customerRuntime: true, firstRunPending: true, pathname: '/settings' }),
    false
  )
})

test('packaged customer mode hides only the legacy Gateway surface', () => {
  assert.equal(hidesLegacyGatewayUi(true, 'gateway'), true)
  assert.equal(hidesLegacyGatewayUi(true, 'server-autocount'), false)
  assert.equal(hidesLegacyGatewayUi(false, 'gateway'), false)
})
