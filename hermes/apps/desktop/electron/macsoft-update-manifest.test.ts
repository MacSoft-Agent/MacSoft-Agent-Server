import assert from 'node:assert/strict'
import { generateKeyPairSync, sign } from 'node:crypto'
import test from 'node:test'

import {
  acceptMacSoftUpdate,
  compareMacSoftVersions,
  MacSoftUpdateError,
  verifyMacSoftUpdateManifest
} from './macsoft-update-manifest'

const keys = generateKeyPairSync('ed25519')
const publicKey = keys.publicKey.export({ format: 'der', type: 'spki' }).toString('base64')

function envelope(overrides: Record<string, unknown> = {}) {
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
      },
      ...overrides
    })
  )
  return JSON.stringify({
    envelope_version: 1,
    algorithm: 'ed25519',
    payload: payload.toString('base64'),
    signature: sign(null, payload, keys.privateKey).toString('base64')
  })
}

test('valid Ed25519 manifest verifies and an upgrade is accepted', () => {
  const release = verifyMacSoftUpdateManifest(envelope(), publicKey)
  assert.equal(release.version, '0.2.0')
  assert.equal(release.installer.bytes, 172_000_000)
  assert.equal(
    acceptMacSoftUpdate(release, { product: 'MacSoft Agent', channel: 'stable', version: '0.1.0' }),
    release
  )
})

test('tampering with the signed payload fails closed', () => {
  const value = JSON.parse(envelope())
  const payload = JSON.parse(Buffer.from(value.payload, 'base64').toString('utf8'))
  payload.version = '9.9.9'
  value.payload = Buffer.from(JSON.stringify(payload)).toString('base64')
  assert.throws(
    () => verifyMacSoftUpdateManifest(JSON.stringify(value), publicKey),
    (error: unknown) =>
      error instanceof MacSoftUpdateError && error.code === 'manifest-signature-invalid'
  )
})

test('a different signing key fails closed', () => {
  const other = generateKeyPairSync('ed25519').publicKey.export({ format: 'der', type: 'spki' }).toString('base64')
  assert.throws(
    () => verifyMacSoftUpdateManifest(envelope(), other),
    (error: unknown) =>
      error instanceof MacSoftUpdateError && error.code === 'manifest-signature-invalid'
  )
})

test('same-version and downgrade releases are rejected', () => {
  const same = verifyMacSoftUpdateManifest(envelope({ version: '0.1.0' }), publicKey)
  assert.throws(
    () => acceptMacSoftUpdate(same, { product: 'MacSoft Agent', channel: 'stable', version: '0.1.0' }),
    (error: unknown) => error instanceof MacSoftUpdateError && error.code === 'release-same-version'
  )
  const older = verifyMacSoftUpdateManifest(envelope({ version: '0.0.9' }), publicKey)
  assert.throws(
    () => acceptMacSoftUpdate(older, { product: 'MacSoft Agent', channel: 'stable', version: '0.1.0' }),
    (error: unknown) => error instanceof MacSoftUpdateError && error.code === 'release-downgrade'
  )
})

test('channel mismatch and unsafe installer URLs are rejected', () => {
  const beta = verifyMacSoftUpdateManifest(envelope({ channel: 'beta' }), publicKey)
  assert.throws(
    () => acceptMacSoftUpdate(beta, { product: 'MacSoft Agent', channel: 'stable', version: '0.1.0' }),
    (error: unknown) =>
      error instanceof MacSoftUpdateError && error.code === 'release-channel-mismatch'
  )
  assert.throws(
    () =>
      verifyMacSoftUpdateManifest(
        envelope({
          installer: {
            url: 'http://updates.example.test/setup.exe',
            sha256: 'a'.repeat(64),
            bytes: 100
          }
        }),
        publicKey
      ),
    (error: unknown) => error instanceof MacSoftUpdateError && error.code === 'manifest-invalid'
  )
})

test('version comparison is numeric and strict', () => {
  assert.equal(compareMacSoftVersions('0.10.0', '0.2.0'), 1)
  assert.equal(compareMacSoftVersions('1.0.0', '1.0.0'), 0)
  assert.throws(() => compareMacSoftVersions('1.0', '1.0.0'))
})
