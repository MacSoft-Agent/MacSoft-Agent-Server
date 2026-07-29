import assert from 'node:assert/strict'
import { generateKeyPairSync, sign } from 'node:crypto'
import test from 'node:test'

import type { TrustedMacSoftRelease } from './macsoft-update-manifest'
import { customerUpdateApply, customerUpdateBranch, customerUpdateCheck } from './macsoft-update-policy'

const baseMetadata = {
  product: 'MacSoft Agent' as const,
  product_version: '0.1.0',
  build_id: 'macsoft-agent-0.1.0-stable.1',
  channel: 'stable',
  update_manifest_url: null,
  update_manifest_public_key: null
}

test('customer update policy stays fail-closed when no trusted feed exists', async () => {
  const status = await customerUpdateCheck(baseMetadata)
  assert.equal(status.supported, false)
  assert.equal(status.error, 'update-not-configured')
  assert.equal(status.manifestConfigured, false)
  assert.deepEqual(customerUpdateBranch(), { branch: 'installer-managed' })
  assert.equal(customerUpdateApply().ok, false)
})

test('configured activation build fails closed while the stable manifest is unavailable', async () => {
  let trustedRelease: TrustedMacSoftRelease | null = {
    buildId: 'stale',
    bytes: 1,
    publishedAt: '2026-07-29T00:00:00.000Z',
    sha256: 'a'.repeat(64),
    url: 'https://updates.example.test/stale.exe',
    version: '9.9.9'
  }
  const status = await customerUpdateCheck(
    {
      ...baseMetadata,
      update_manifest_url: 'https://updates.example.test/manifest.json',
      update_manifest_public_key: 'ZmFrZQ=='
    },
    {
      packaged: true,
      fetchManifest: async () => { throw new Error('404') },
      onTrustedRelease: release => { trustedRelease = release }
    }
  )
  assert.equal(status.supported, false)
  assert.equal(status.updateAvailable, false)
  assert.equal(status.error, 'update-check-failed')
  assert.equal(status.manifestConfigured, true)
  assert.equal(trustedRelease, null)
})

test('configured source is not contacted outside a packaged build', async () => {
  let fetched = false
  const status = await customerUpdateCheck(
    {
      ...baseMetadata,
      update_manifest_url: 'https://updates.example.test/manifest.json',
      update_manifest_public_key: 'ZmFrZQ=='
    },
    {
      packaged: false,
      fetchManifest: async () => {
        fetched = true
        return ''
      }
    }
  )
  assert.equal(status.error, 'packaged-only')
  assert.equal(fetched, false)
})

test('packaged check reports only a correctly signed upgrade', async () => {
  const keys = generateKeyPairSync('ed25519')
  const payload = Buffer.from(
    JSON.stringify({
      schema_version: 1,
      product: 'MacSoft Agent',
      channel: 'stable',
      version: '0.2.0',
      build_id: 'macsoft-agent-0.2.0-stable.1',
      published_at: '2026-07-28T00:00:00.000Z',
      installer: {
        url: 'https://updates.example.test/MacSoft-Agent-Setup-0.2.0.exe',
        sha256: 'a'.repeat(64),
        bytes: 172_000_000
      }
    })
  )
  const manifest = JSON.stringify({
    envelope_version: 1,
    algorithm: 'ed25519',
    payload: payload.toString('base64'),
    signature: sign(null, payload, keys.privateKey).toString('base64')
  })
  let trustedRelease: TrustedMacSoftRelease | null = null
  const status = await customerUpdateCheck(
    {
      ...baseMetadata,
      update_manifest_url: 'https://updates.example.test/manifest.json',
      update_manifest_public_key: keys.publicKey.export({ format: 'der', type: 'spki' }).toString('base64')
    },
    {
      packaged: true,
      fetchManifest: async () => manifest,
      onTrustedRelease: release => {
        trustedRelease = release
      },
      now: () => 123
    }
  )
  assert.equal(status.supported, true)
  assert.equal(status.updateAvailable, true)
  assert.equal(status.targetVersion, '0.2.0')
  assert.equal(status.targetBuildId, 'macsoft-agent-0.2.0-stable.1')
  assert.equal(status.fetchedAt, 123)
  assert.equal(trustedRelease?.version, '0.2.0')

  const sameVersion = await customerUpdateCheck(
    {
      ...baseMetadata,
      product_version: '0.2.0',
      update_manifest_url: 'https://updates.example.test/manifest.json',
      update_manifest_public_key: keys.publicKey.export({ format: 'der', type: 'spki' }).toString('base64')
    },
    {
      packaged: true,
      fetchManifest: async () => manifest
    }
  )
  assert.equal(sameVersion.supported, true)
  assert.equal(sameVersion.updateAvailable, false)
  assert.equal(sameVersion.error, undefined)
  assert.equal(sameVersion.message, 'MacSoft Agent is up to date.')
})
