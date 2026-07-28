import assert from 'node:assert/strict'
import { generateKeyPairSync } from 'node:crypto'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { buildManifest, parseArguments } from './build-update-manifest.mjs'

test('release manifest builder signs exact product and installer metadata', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'macsoft-update-manifest-'))
  try {
    const keys = generateKeyPairSync('ed25519')
    const product = path.join(root, 'product.json')
    const installer = path.join(root, 'installer.exe')
    const privateKey = path.join(root, 'update-private.pem')
    await writeFile(
      product,
      JSON.stringify({
        product: 'MacSoft Agent',
        product_version: '0.2.0',
        channel: 'stable',
        build_id: 'macsoft-agent-0.2.0-stable.1'
      })
    )
    await writeFile(installer, 'installer')
    await writeFile(privateKey, keys.privateKey.export({ format: 'pem', type: 'pkcs8' }))

    const result = await buildManifest({
      product,
      installer,
      privateKey,
      installerUrl: 'https://updates.example.test/MacSoft-Agent-Setup-0.2.0.exe'
    })
    assert.equal(result.envelope.algorithm, 'ed25519')
    const payload = JSON.parse(Buffer.from(result.envelope.payload, 'base64').toString('utf8'))
    assert.equal(payload.version, '0.2.0')
    assert.equal(payload.installer.bytes, 9)
    assert.equal(result.publicKeySpkiBase64, keys.publicKey.export({ format: 'der', type: 'spki' }).toString('base64'))
  } finally {
    await rm(root, { force: true, recursive: true })
  }
})

test('argument parser requires explicit release inputs', () => {
  assert.throws(() => parseArguments(['--installer', 'x']), /--installer-url is required/)
  assert.throws(
    () => parseArguments(['--installer', 'x', '--installer', 'y']),
    /provided more than once/
  )
  assert.throws(
    () => parseArguments(['--unknown', 'x']),
    /Unknown argument/
  )
})
