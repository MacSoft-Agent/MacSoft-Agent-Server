import assert from 'node:assert/strict'
import { createHash, generateKeyPairSync, sign } from 'node:crypto'
import { readFile, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import {
  MacSoftUpdateDownloadError,
  writeVerifiedMacSoftInstaller
} from './macsoft-update-download'
import { verifyMacSoftUpdateManifest } from './macsoft-update-manifest'

function releaseFor(bytes: Buffer, overrides: Record<string, unknown> = {}) {
  const { privateKey, publicKey } = generateKeyPairSync('ed25519')
  const payload = Buffer.from(
    JSON.stringify({
      schema_version: 1,
      product: 'MacSoft Agent',
      channel: 'stable',
      version: '0.2.0',
      build_id: 'macsoft-agent-0.2.0-test',
      published_at: '2026-07-28T00:00:00.000Z',
      installer: {
        url: 'https://updates.example.invalid/MacSoft-Agent-Setup.exe',
        sha256: createHash('sha256').update(bytes).digest('hex'),
        bytes: bytes.length,
        ...overrides
      }
    })
  )
  return verifyMacSoftUpdateManifest(
    JSON.stringify({
      envelope_version: 1,
      algorithm: 'ed25519',
      payload: payload.toString('base64'),
      signature: sign(null, payload, privateKey).toString('base64')
    }),
    publicKey.export({ format: 'der', type: 'spki' }).toString('base64')
  )
}

function bodyFor(bytes: Buffer): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      controller.enqueue(bytes)
      controller.close()
    }
  })
}

test('verified installer is atomically published after size and SHA-256 match', async () => {
  const root = path.join(os.tmpdir(), `macsoft-update-download-${process.pid}-${Date.now()}`)
  const bytes = Buffer.from('trusted-installer')
  try {
    const result = await writeVerifiedMacSoftInstaller(
      { body: bodyFor(bytes), contentLength: bytes.length },
      releaseFor(bytes),
      root
    )
    assert.equal(result.bytes, bytes.length)
    assert.equal(await readFile(result.path, 'utf8'), bytes.toString('utf8'))
    assert.equal(result.sha256, createHash('sha256').update(bytes).digest('hex'))
  } finally {
    await rm(root, { force: true, recursive: true })
  }
})

test('declared or actual size mismatch is rejected and partial file is removed', async () => {
  const root = path.join(os.tmpdir(), `macsoft-update-download-size-${process.pid}-${Date.now()}`)
  const bytes = Buffer.from('trusted-installer')
  try {
    await assert.rejects(
      writeVerifiedMacSoftInstaller(
        { body: bodyFor(bytes), contentLength: bytes.length + 1 },
        releaseFor(bytes),
        root
      ),
      (error: unknown) =>
        error instanceof MacSoftUpdateDownloadError && error.code === 'installer-size-mismatch'
    )
    await assert.rejects(
      writeVerifiedMacSoftInstaller(
        { body: bodyFor(Buffer.concat([bytes, Buffer.from('extra')])) },
        releaseFor(bytes),
        root
      ),
      (error: unknown) =>
        error instanceof MacSoftUpdateDownloadError && error.code === 'installer-size-mismatch'
    )
  } finally {
    await rm(root, { force: true, recursive: true })
  }
})

test('oversized download cancels the underlying web stream', async () => {
  const root = path.join(os.tmpdir(), `macsoft-update-download-cancel-${process.pid}-${Date.now()}`)
  const bytes = Buffer.from('trusted-installer')
  let cancelled = false
  const body = new ReadableStream<Uint8Array>({
    cancel() {
      cancelled = true
    },
    start(controller) {
      controller.enqueue(Buffer.concat([bytes, Buffer.from('extra')]))
    }
  })
  try {
    await assert.rejects(
      writeVerifiedMacSoftInstaller({ body }, releaseFor(bytes), root),
      (error: unknown) =>
        error instanceof MacSoftUpdateDownloadError && error.code === 'installer-size-mismatch'
    )
    assert.equal(cancelled, true)
  } finally {
    await rm(root, { force: true, recursive: true })
  }
})

test('SHA-256 mismatch is rejected and installer is not published', async () => {
  const root = path.join(os.tmpdir(), `macsoft-update-download-hash-${process.pid}-${Date.now()}`)
  const bytes = Buffer.from('trusted-installer')
  try {
    await assert.rejects(
      writeVerifiedMacSoftInstaller(
        { body: bodyFor(Buffer.from('untrusted-content')) },
        releaseFor(Buffer.from('untrusted-content'), {
          sha256: createHash('sha256').update(bytes).digest('hex')
        }),
        root
      ),
      (error: unknown) =>
        error instanceof MacSoftUpdateDownloadError && error.code === 'installer-hash-mismatch'
    )
  } finally {
    await rm(root, { force: true, recursive: true })
  }
})
