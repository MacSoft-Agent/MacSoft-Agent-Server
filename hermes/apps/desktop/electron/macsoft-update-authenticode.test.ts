import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

import {
  MacSoftAuthenticodeError,
  verifyMacSoftInstallerAuthenticode
} from './macsoft-update-authenticode'

test('valid Windows Authenticode result is accepted without exposing signer details', () => {
  const result = verifyMacSoftInstallerAuthenticode(
    'C:\\Temp\\MacSoft-Agent-Setup.exe',
    'powershell.exe',
    (_file, _args, options) => {
      assert.equal(
        options.env?.MACSOFT_UPDATE_INSTALLER_PATH,
        'C:\\Temp\\MacSoft-Agent-Setup.exe'
      )
      return JSON.stringify({
        status: 'Valid',
        subject: 'CN=Mac Soft',
        thumbprint: 'AA'.repeat(20)
      })
    }
  )
  assert.equal(result.status, 'Valid')
})

test(
  'generated probe executes in real Windows PowerShell',
  { skip: process.platform !== 'win32' },
  () => {
    assert.throws(
      () =>
        verifyMacSoftInstallerAuthenticode(
          fileURLToPath(import.meta.url),
          'powershell.exe'
        ),
      (error: unknown) =>
        error instanceof MacSoftAuthenticodeError &&
        error.message ===
          'The update installer is not Authenticode-signed with a valid Windows certificate.'
    )
  }
)

test('unsigned, invalid or malformed results fail closed', () => {
  for (const output of [
    JSON.stringify({ status: 'NotSigned', subject: '', thumbprint: '' }),
    JSON.stringify({ status: 'HashMismatch', subject: 'CN=Mac Soft', thumbprint: 'AA'.repeat(20) }),
    'not-json'
  ]) {
    assert.throws(
      () =>
        verifyMacSoftInstallerAuthenticode(
          'C:\\Temp\\MacSoft-Agent-Setup.exe',
          'powershell.exe',
          () => output
        ),
      (error: unknown) =>
        error instanceof MacSoftAuthenticodeError &&
        error.code === 'installer-signature-invalid'
    )
  }
})
