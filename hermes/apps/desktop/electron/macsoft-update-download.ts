import { createHash } from 'node:crypto'
import { createWriteStream } from 'node:fs'
import { mkdir, rename, rm } from 'node:fs/promises'
import path from 'node:path'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'

import { MAX_INSTALLER_BYTES, type TrustedMacSoftRelease } from './macsoft-update-manifest'

export type MacSoftUpdateDownloadErrorCode =
  | 'installer-download-failed'
  | 'installer-size-mismatch'
  | 'installer-hash-mismatch'

export class MacSoftUpdateDownloadError extends Error {
  constructor(
    readonly code: MacSoftUpdateDownloadErrorCode,
    message: string
  ) {
    super(message)
    this.name = 'MacSoftUpdateDownloadError'
  }
}

export interface DownloadedMacSoftInstaller {
  bytes: number
  path: string
  sha256: string
}

export interface MacSoftUpdateDownloadSource {
  body: ReadableStream<Uint8Array>
  contentLength?: number
}

function safeSegment(value: string): string {
  const segment = value.replace(/[^A-Za-z0-9._-]/g, '_')
  if (!segment || segment === '.' || segment === '..') {
    throw new MacSoftUpdateDownloadError(
      'installer-download-failed',
      'Update release contains an invalid file identifier.'
    )
  }
  return segment
}

export async function writeVerifiedMacSoftInstaller(
  source: MacSoftUpdateDownloadSource,
  release: TrustedMacSoftRelease,
  updateRoot: string
): Promise<DownloadedMacSoftInstaller> {
  const expectedBytes = release.installer.bytes
  if (
    !Number.isSafeInteger(expectedBytes) ||
    expectedBytes < 1 ||
    expectedBytes > MAX_INSTALLER_BYTES ||
    (source.contentLength !== undefined && source.contentLength !== expectedBytes)
  ) {
    throw new MacSoftUpdateDownloadError(
      'installer-size-mismatch',
      'Downloaded installer size does not match the trusted update manifest.'
    )
  }

  const releaseDirectory = path.join(
    updateRoot,
    `${safeSegment(release.version)}-${safeSegment(release.buildId)}`
  )
  const finalPath = path.join(releaseDirectory, 'MacSoft-Agent-Setup.exe')
  const partialPath = `${finalPath}.part`
  await mkdir(releaseDirectory, { recursive: true })
  await rm(partialPath, { force: true })

  const hash = createHash('sha256')
  let bytes = 0
  const input = Readable.fromWeb(source.body)
  input.on('data', (chunk: Buffer) => {
    bytes += chunk.length
    if (bytes > expectedBytes || bytes > MAX_INSTALLER_BYTES) {
      input.destroy(
        new MacSoftUpdateDownloadError(
          'installer-size-mismatch',
          'Downloaded installer exceeded the trusted size.'
        )
      )
      return
    }
    hash.update(chunk)
  })

  try {
    await pipeline(input, createWriteStream(partialPath, { flags: 'wx' }))
    if (bytes !== expectedBytes) {
      throw new MacSoftUpdateDownloadError(
        'installer-size-mismatch',
        'Downloaded installer size does not match the trusted update manifest.'
      )
    }
    const sha256 = hash.digest('hex')
    if (sha256 !== release.installer.sha256) {
      throw new MacSoftUpdateDownloadError(
        'installer-hash-mismatch',
        'Downloaded installer SHA-256 does not match the trusted update manifest.'
      )
    }
    await rm(finalPath, { force: true })
    await rename(partialPath, finalPath)
    return { bytes, path: finalPath, sha256 }
  } catch (error) {
    await rm(partialPath, { force: true })
    if (error instanceof MacSoftUpdateDownloadError) throw error
    throw new MacSoftUpdateDownloadError(
      'installer-download-failed',
      'MacSoft Agent could not save the update installer.'
    )
  }
}
