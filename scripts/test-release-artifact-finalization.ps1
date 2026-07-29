[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$finalizer = Join-Path $PSScriptRoot 'finalize-release-artifact.ps1'

. $finalizer -InstallerPath 'unused' -ArtifactMode InternalTestUnsigned

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

$testRoot = Join-Path ([IO.Path]::GetTempPath()) "macsoft-release-finalization-$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $testRoot | Out-Null

try {
    $installer = Join-Path $testRoot 'installer.exe'
    $signer = Join-Path $testRoot 'external-signer.cmd'
    $signTool = Join-Path $testRoot 'signtool.exe'
    [IO.File]::WriteAllBytes($installer, [Text.Encoding]::UTF8.GetBytes('unsigned-installer'))
    Set-Content -LiteralPath $signer -Value '@exit /b 0' -Encoding ascii
    Set-Content -LiteralPath $signTool -Value 'test verifier placeholder' -Encoding ascii

    $unsignedProbe = {
        param($Path)
        [pscustomobject]@{
            Status = 'NotSigned'
            SignerCertificate = $null
            TimeStamperCertificate = $null
        }
    }
    $validProbe = {
        param($Path)
        [pscustomobject]@{
            Status = 'Valid'
            SignerCertificate = [pscustomobject]@{
                Subject = 'CN=MacSoft Test Signer'
                Thumbprint = 'AABBCC'
            }
            TimeStamperCertificate = [pscustomobject]@{
                Subject = 'CN=MacSoft Test Timestamp'
                Thumbprint = 'DDEEFF'
            }
        }
    }
    $noTimestampProbe = {
        param($Path)
        [pscustomobject]@{
            Status = 'Valid'
            SignerCertificate = [pscustomobject]@{
                Subject = 'CN=MacSoft Test Signer'
                Thumbprint = 'AABBCC'
            }
            TimeStamperCertificate = $null
        }
    }
    $invalidProbe = {
        param($Path)
        [pscustomobject]@{
            Status = 'HashMismatch'
            SignerCertificate = [pscustomobject]@{
                Subject = 'CN=MacSoft Test Signer'
                Thumbprint = 'AABBCC'
            }
            TimeStamperCertificate = $null
        }
    }
    $noOpVerifier = { param($Tool, $Path) }

    $unsigned = Complete-ReleaseArtifact `
        -ArtifactPath $installer `
        -Mode InternalTestUnsigned `
        -AuthenticodeProbe $unsignedProbe
    Assert-Condition ($unsigned.artifact_class -eq 'internal-test-unsigned') 'Unsigned artifact classification failed.'
    Assert-Condition (-not $unsigned.production_ready) 'Unsigned artifacts must never be production-ready.'
    Assert-Condition ($unsigned.installer_sha256 -eq (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()) 'Unsigned artifact hash mismatch.'

    Assert-Throws -Pattern 'requires an external signing command' -Action {
        Complete-ReleaseArtifact `
            -ArtifactPath $installer `
            -Mode Production `
            -AuthenticodeProbe $validProbe `
            -NativeVerifier $noOpVerifier
    }

    $failingSigner = { param($Command, $Path) throw 'simulated signing failure' }
    Assert-Throws -Pattern 'simulated signing failure' -Action {
        Complete-ReleaseArtifact `
            -ArtifactPath $installer `
            -Mode Production `
            -ExternalSigningCommand $signer `
            -RequestedSignTool $signTool `
            -SignerInvoker $failingSigner `
            -AuthenticodeProbe $validProbe `
            -NativeVerifier $noOpVerifier
    }

    $noOpSigner = { param($Command, $Path) }
    Assert-Throws -Pattern 'status is not Valid' -Action {
        Complete-ReleaseArtifact `
            -ArtifactPath $installer `
            -Mode Production `
            -ExternalSigningCommand $signer `
            -RequestedSignTool $signTool `
            -SignerInvoker $noOpSigner `
            -AuthenticodeProbe $invalidProbe `
            -NativeVerifier $noOpVerifier
    }
    Assert-Throws -Pattern 'trusted timestamp' -Action {
        Complete-ReleaseArtifact `
            -ArtifactPath $installer `
            -Mode Production `
            -ExternalSigningCommand $signer `
            -RequestedSignTool $signTool `
            -SignerInvoker $noOpSigner `
            -AuthenticodeProbe $noTimestampProbe `
            -NativeVerifier $noOpVerifier
    }

    $failingVerifier = { param($Tool, $Path) throw 'simulated native verification failure' }
    Assert-Throws -Pattern 'simulated native verification failure' -Action {
        Complete-ReleaseArtifact `
            -ArtifactPath $installer `
            -Mode Production `
            -ExternalSigningCommand $signer `
            -RequestedSignTool $signTool `
            -SignerInvoker $noOpSigner `
            -AuthenticodeProbe $validProbe `
            -NativeVerifier $failingVerifier
    }

    $signingMutation = {
        param($Command, $Path)
        [IO.File]::AppendAllText($Path, '-signed')
    }
    $signed = Complete-ReleaseArtifact `
        -ArtifactPath $installer `
        -Mode Production `
        -ExternalSigningCommand $signer `
        -RequestedSignTool $signTool `
        -SignerInvoker $signingMutation `
        -AuthenticodeProbe $validProbe `
        -NativeVerifier $noOpVerifier
    Assert-Condition ($signed.artifact_class -eq 'production-signed') 'Production artifact classification failed.'
    Assert-Condition $signed.production_ready 'A valid signed artifact should be production-ready.'
    Assert-Condition $signed.timestamped 'A production artifact must record a timestamp.'
    Assert-Condition ($signed.installer_sha256 -eq (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()) 'The production hash was not calculated from post-sign bytes.'
    Assert-Condition ($signed.installer_bytes -eq (Get-Item -LiteralPath $installer).Length) 'The production byte count was not calculated from post-sign bytes.'

    Assert-Throws -Pattern 'does not accept a signing command' -Action {
        Complete-ReleaseArtifact `
            -ArtifactPath $installer `
            -Mode InternalTestUnsigned `
            -ExternalSigningCommand $signer `
            -AuthenticodeProbe $unsignedProbe
    }

    Assert-Throws -Pattern 'outside the source repository' -Action {
        Complete-ReleaseArtifact `
            -ArtifactPath $installer `
            -Mode Production `
            -ExternalSigningCommand $finalizer `
            -RequestedSignTool $signTool `
            -SignerInvoker $noOpSigner `
            -AuthenticodeProbe $validProbe `
            -NativeVerifier $noOpVerifier
    }

    Write-Host 'Release artifact finalization tests passed.'
}
finally {
    Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
}
