import assert from 'node:assert/strict'
import test from 'node:test'

import { customerUpdateApply, customerUpdateBranch, customerUpdateCheck } from './macsoft-update-policy'

test('customer update policy is installer-only when no MacSoft feed exists', () => {
  const status = customerUpdateCheck({ update_manifest_url: null })
  assert.equal(status.supported, false)
  assert.equal(status.error, 'installer-managed')
  assert.equal(status.manifestConfigured, false)
  assert.deepEqual(customerUpdateBranch(), { branch: 'installer-managed' })
  assert.equal(customerUpdateApply().ok, false)
})

test('customer update check has no network dependency or upstream fallback', () => {
  assert.equal(customerUpdateCheck.length, 1)
  const source = customerUpdateCheck.toString()
  assert.doesNotMatch(source, /\b(fetch|git|github|upstream)\b/i)
})
