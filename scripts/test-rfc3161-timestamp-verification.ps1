[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$verifier = Join-Path $PSScriptRoot 'verify-rfc3161-timestamp.ps1'
. $verifier -InstallerPath 'unused'

function Assert-Condition {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Throws {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action,

        [Parameter(Mandatory = $true)]
        [string]$Pattern
    )

    try {
        & $Action
    }
    catch {
        if ($_.Exception.Message -notmatch $Pattern) {
            throw "Expected error matching '$Pattern', received: $($_.Exception.Message)"
        }
        return
    }
    throw "Expected error matching '$Pattern', but no error was raised."
}

function New-TestCmsEvidence {
    param(
        [int]$Rfc3161Count = 1,
        [int]$LegacyCount = 0,
        [int]$NestedSignatureCount = 0,
        [int]$ValueCount = 1
    )

    [pscustomobject]@{
        rfc3161_attribute_count = $Rfc3161Count
        legacy_attribute_count = $LegacyCount
        nested_signature_attribute_count = $NestedSignatureCount
        rfc3161_value_count = $ValueCount
        timestamp_content_info = [byte[]]@(0x30, 0x00)
        signed_data = [byte[]]@(0x01, 0x02, 0x03)
    }
}

$sha256NativeVerifier = {
    param($TimestampContentInfo, $SignedData)
    Assert-Condition ($TimestampContentInfo.Length -gt 0) 'Timestamp token was not supplied.'
    Assert-Condition ($SignedData.Length -gt 0) 'Signer signature was not supplied.'
    '2.16.840.1.101.3.4.2.1'
}
$validReader = { param($Path) New-TestCmsEvidence }

$valid = Get-Rfc3161TimestampEvidence `
    -Path 'test-only.exe' `
    -CmsEvidenceReader $validReader `
    -NativeVerifier $sha256NativeVerifier
Assert-Condition $valid.rfc3161_verified 'Valid RFC 3161 evidence was not accepted.'
Assert-Condition ($valid.message_imprint_digest -eq 'sha256') 'SHA-256 evidence was not recorded.'

Assert-Throws -Pattern 'does not contain an RFC 3161 timestamp' -Action {
    Get-Rfc3161TimestampEvidence `
        -Path 'test-only.exe' `
        -CmsEvidenceReader { param($Path) New-TestCmsEvidence -Rfc3161Count 0 } `
        -NativeVerifier $sha256NativeVerifier
}

Assert-Throws -Pattern 'only a legacy Authenticode timestamp' -Action {
    Get-Rfc3161TimestampEvidence `
        -Path 'test-only.exe' `
        -CmsEvidenceReader {
            param($Path)
            New-TestCmsEvidence -Rfc3161Count 0 -LegacyCount 1
        } `
        -NativeVerifier $sha256NativeVerifier
}

Assert-Throws -Pattern 'ambiguous legacy and RFC 3161' -Action {
    Get-Rfc3161TimestampEvidence `
        -Path 'test-only.exe' `
        -CmsEvidenceReader { param($Path) New-TestCmsEvidence -LegacyCount 1 } `
        -NativeVerifier $sha256NativeVerifier
}

Assert-Throws -Pattern 'unsupported nested Authenticode signature' -Action {
    Get-Rfc3161TimestampEvidence `
        -Path 'test-only.exe' `
        -CmsEvidenceReader {
            param($Path)
            New-TestCmsEvidence -NestedSignatureCount 1
        } `
        -NativeVerifier $sha256NativeVerifier
}

Assert-Throws -Pattern 'malformed or ambiguous' -Action {
    Get-Rfc3161TimestampEvidence `
        -Path 'test-only.exe' `
        -CmsEvidenceReader { param($Path) New-TestCmsEvidence -ValueCount 2 } `
        -NativeVerifier $sha256NativeVerifier
}

Assert-Throws -Pattern 'timestamp verification failed' -Action {
    Get-Rfc3161TimestampEvidence `
        -Path 'test-only.exe' `
        -CmsEvidenceReader $validReader `
        -NativeVerifier {
            param($TimestampContentInfo, $SignedData)
            throw 'simulated native verifier failure'
        }
}

Assert-Throws -Pattern 'message-imprint digest is not approved' -Action {
    Get-Rfc3161TimestampEvidence `
        -Path 'test-only.exe' `
        -CmsEvidenceReader $validReader `
        -NativeVerifier { param($TimestampContentInfo, $SignedData) '1.3.14.3.2.26' }
}

Write-Host 'RFC 3161 timestamp verification tests passed.'
