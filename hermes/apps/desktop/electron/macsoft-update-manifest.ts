import { createPublicKey, verify } from 'node:crypto'

export const MACSOFT_UPDATE_ENVELOPE_VERSION = 1
export const MACSOFT_UPDATE_PAYLOAD_SCHEMA = 1
export const MAX_UPDATE_MANIFEST_BYTES = 64 * 1024
export const MAX_INSTALLER_BYTES = 2 * 1024 * 1024 * 1024

const SHA256_PATTERN = /^[0-9a-f]{64}$/
const VERSION_PATTERN = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/
const BASE64_PATTERN = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/

export type MacSoftUpdateErrorCode =
  | 'manifest-invalid'
  | 'manifest-signature-invalid'
  | 'release-channel-mismatch'
  | 'release-downgrade'
  | 'release-same-version'

export class MacSoftUpdateError extends Error {
  constructor(
    readonly code: MacSoftUpdateErrorCode,
    message: string
  ) {
    super(message)
    this.name = 'MacSoftUpdateError'
  }
}

export interface TrustedMacSoftRelease {
  buildId: string
  channel: string
  installer: {
    bytes: number
    sha256: string
    url: string
  }
  product: 'MacSoft Agent'
  publishedAt: string
  schemaVersion: 1
  version: string
}

export interface CurrentMacSoftRelease {
  channel: string
  product: 'MacSoft Agent'
  version: string
}

function fail(message: string): never {
  throw new MacSoftUpdateError('manifest-invalid', message)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort()
  const expected = [...keys].sort()
  return actual.length === expected.length && actual.every((key, index) => key === expected[index])
}

function decodeBase64(value: unknown, field: string, maximumBytes: number): Buffer {
  if (typeof value !== 'string' || value.length === 0 || !BASE64_PATTERN.test(value)) {
    fail(`${field} must be canonical base64.`)
  }
  const decoded = Buffer.from(value, 'base64')
  if (decoded.length === 0 || decoded.length > maximumBytes || decoded.toString('base64') !== value) {
    fail(`${field} is outside the supported size or encoding.`)
  }
  return decoded
}

function requiredText(value: unknown, field: string, maximumLength = 256): string {
  if (typeof value !== 'string' || !value.trim() || value !== value.trim() || value.length > maximumLength) {
    fail(`${field} must be non-empty normalized text.`)
  }
  return value
}

function parseHttpsUrl(value: unknown): string {
  const text = requiredText(value, 'installer.url', 2048)
  let parsed: URL
  try {
    parsed = new URL(text)
  } catch {
    fail('installer.url must be a valid HTTPS URL.')
  }
  if (
    parsed.protocol !== 'https:' ||
    parsed.username ||
    parsed.password ||
    parsed.hash ||
    parsed.toString() !== text
  ) {
    fail('installer.url must be a normalized HTTPS URL without credentials or a fragment.')
  }
  return text
}

function parseVersion(value: unknown, field: string): [number, number, number] {
  if (typeof value !== 'string') fail(`${field} must use major.minor.patch format.`)
  const match = VERSION_PATTERN.exec(value)
  if (!match) fail(`${field} must use major.minor.patch format.`)
  const parts = match.slice(1).map(Number) as [number, number, number]
  if (parts.some(part => !Number.isSafeInteger(part) || part > 1_000_000)) {
    fail(`${field} contains an unsupported numeric component.`)
  }
  return parts
}

export function compareMacSoftVersions(left: string, right: string): number {
  const a = parseVersion(left, 'version')
  const b = parseVersion(right, 'current version')
  for (let index = 0; index < a.length; index += 1) {
    if (a[index] !== b[index]) return a[index] < b[index] ? -1 : 1
  }
  return 0
}

function parseReleasePayload(payloadBytes: Buffer): TrustedMacSoftRelease {
  let value: unknown
  try {
    value = JSON.parse(payloadBytes.toString('utf8'))
  } catch {
    fail('Signed update payload is not valid JSON.')
  }
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ['schema_version', 'product', 'channel', 'version', 'build_id', 'published_at', 'installer'])
  ) {
    fail('Signed update payload fields do not match schema version 1.')
  }
  if (value.schema_version !== MACSOFT_UPDATE_PAYLOAD_SCHEMA) {
    fail('Signed update payload schema is unsupported.')
  }
  if (value.product !== 'MacSoft Agent') fail('Signed update payload identifies another product.')
  const channel = requiredText(value.channel, 'channel', 32)
  const version = requiredText(value.version, 'version', 64)
  parseVersion(version, 'version')
  const buildId = requiredText(value.build_id, 'build_id', 128)
  const publishedAt = requiredText(value.published_at, 'published_at', 64)
  const timestamp = Date.parse(publishedAt)
  if (!Number.isFinite(timestamp) || new Date(timestamp).toISOString() !== publishedAt) {
    fail('published_at must be a canonical UTC ISO-8601 timestamp.')
  }
  if (!isRecord(value.installer) || !hasExactKeys(value.installer, ['url', 'sha256', 'bytes'])) {
    fail('installer fields do not match schema version 1.')
  }
  const bytes = value.installer.bytes
  if (!Number.isSafeInteger(bytes) || Number(bytes) < 1 || Number(bytes) > MAX_INSTALLER_BYTES) {
    fail('installer.bytes is outside the supported range.')
  }
  const sha256 = requiredText(value.installer.sha256, 'installer.sha256', 64)
  if (!SHA256_PATTERN.test(sha256)) fail('installer.sha256 must be a lowercase SHA-256 digest.')
  return {
    buildId,
    channel,
    installer: {
      bytes: Number(bytes),
      sha256,
      url: parseHttpsUrl(value.installer.url)
    },
    product: 'MacSoft Agent',
    publishedAt,
    schemaVersion: 1,
    version
  }
}

export function verifyMacSoftUpdateManifest(
  manifestText: string,
  publicKeySpkiBase64: string
): TrustedMacSoftRelease {
  if (Buffer.byteLength(manifestText, 'utf8') > MAX_UPDATE_MANIFEST_BYTES) {
    fail('Update manifest exceeds the supported size.')
  }
  let envelope: unknown
  try {
    envelope = JSON.parse(manifestText)
  } catch {
    fail('Update manifest is not valid JSON.')
  }
  if (
    !isRecord(envelope) ||
    !hasExactKeys(envelope, ['envelope_version', 'algorithm', 'payload', 'signature']) ||
    envelope.envelope_version !== MACSOFT_UPDATE_ENVELOPE_VERSION ||
    envelope.algorithm !== 'ed25519'
  ) {
    fail('Update manifest envelope is unsupported.')
  }
  const payload = decodeBase64(envelope.payload, 'payload', 32 * 1024)
  const signature = decodeBase64(envelope.signature, 'signature', 256)
  const publicKeyBytes = decodeBase64(publicKeySpkiBase64, 'update public key', 1024)
  let publicKey
  try {
    publicKey = createPublicKey({ key: publicKeyBytes, format: 'der', type: 'spki' })
  } catch {
    fail('Embedded update public key is invalid.')
  }
  if (publicKey.asymmetricKeyType !== 'ed25519' || !verify(null, payload, publicKey, signature)) {
    throw new MacSoftUpdateError(
      'manifest-signature-invalid',
      'Update manifest signature could not be verified.'
    )
  }
  return parseReleasePayload(payload)
}

export function acceptMacSoftUpdate(
  release: TrustedMacSoftRelease,
  current: CurrentMacSoftRelease
): TrustedMacSoftRelease {
  if (release.product !== current.product || release.channel !== current.channel) {
    throw new MacSoftUpdateError(
      'release-channel-mismatch',
      'Update release does not match this product channel.'
    )
  }
  const comparison = compareMacSoftVersions(release.version, current.version)
  if (comparison < 0) {
    throw new MacSoftUpdateError('release-downgrade', 'Update release is older than the installed version.')
  }
  if (comparison === 0) {
    throw new MacSoftUpdateError(
      'release-same-version',
      'Update release has the same version as the installed product.'
    )
  }
  return release
}
