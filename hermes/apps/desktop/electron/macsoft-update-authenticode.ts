import { execFileSync, type ExecFileSyncOptionsWithStringEncoding } from 'node:child_process'

export class MacSoftAuthenticodeError extends Error {
  readonly code = 'installer-signature-invalid'

  constructor(message: string) {
    super(message)
    this.name = 'MacSoftAuthenticodeError'
  }
}

interface AuthenticodeProbe {
  status: string
  subject: string
  thumbprint: string
}

type ExecFile = (
  file: string,
  args: readonly string[],
  options: ExecFileSyncOptionsWithStringEncoding
) => string

const AUTHENTICODE_PROBE = [
  "$signature = Get-AuthenticodeSignature -LiteralPath $env:MACSOFT_UPDATE_INSTALLER_PATH",
  '[pscustomobject]@{',
  "  status = [string]$signature.Status",
  "  subject = [string]$signature.SignerCertificate.Subject",
  "  thumbprint = [string]$signature.SignerCertificate.Thumbprint",
  '} | ConvertTo-Json -Compress'
].join('; ')

function parseProbe(value: string): AuthenticodeProbe {
  let parsed: unknown
  try {
    parsed = JSON.parse(value)
  } catch {
    throw new MacSoftAuthenticodeError('Windows did not return a valid installer signature result.')
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new MacSoftAuthenticodeError('Windows did not return an installer signature object.')
  }
  const record = parsed as Record<string, unknown>
  const status = typeof record.status === 'string' ? record.status : ''
  const subject = typeof record.subject === 'string' ? record.subject.trim() : ''
  const thumbprint =
    typeof record.thumbprint === 'string'
      ? record.thumbprint.replaceAll(/\s/g, '').toUpperCase()
      : ''
  if (status !== 'Valid' || !subject || !/^[0-9A-F]{40,128}$/.test(thumbprint)) {
    throw new MacSoftAuthenticodeError(
      'The update installer is not Authenticode-signed with a valid Windows certificate.'
    )
  }
  return { status, subject, thumbprint }
}

export function verifyMacSoftInstallerAuthenticode(
  installerPath: string,
  powershellPath: string,
  execute: ExecFile = execFileSync
): AuthenticodeProbe {
  try {
    const output = execute(
      powershellPath,
      [
        '-NoLogo',
        '-NoProfile',
        '-NonInteractive',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        AUTHENTICODE_PROBE
      ],
      {
        encoding: 'utf8',
        env: {
          ...process.env,
          MACSOFT_UPDATE_INSTALLER_PATH: installerPath
        },
        maxBuffer: 64 * 1024,
        timeout: 30_000,
        windowsHide: true
      }
    )
    return parseProbe(output)
  } catch (error) {
    if (error instanceof MacSoftAuthenticodeError) throw error
    throw new MacSoftAuthenticodeError('Windows could not verify the update installer signature.')
  }
}
