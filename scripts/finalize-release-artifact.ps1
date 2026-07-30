[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,

    [Parameter(Mandatory = $true)]
    [ValidateSet('Production', 'InternalTestUnsigned')]
    [string]$ArtifactMode,

    [string]$SigningCommandPath,

    [string]$SignToolPath
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))

function Test-PathWithinRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $candidate = [IO.Path]::GetFullPath($Path)
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    return $candidate.StartsWith($rootPath, [StringComparison]::OrdinalIgnoreCase)
}

function Resolve-ReleaseSignTool {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        $resolved = [IO.Path]::GetFullPath($RequestedPath)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw 'The requested signtool.exe was not found.'
        }
        return $resolved
    }

    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $kitsRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    if (Test-Path -LiteralPath $kitsRoot -PathType Container) {
        $candidate = Get-ChildItem -LiteralPath $kitsRoot -Recurse -File -Filter signtool.exe |
            Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
            Sort-Object FullName -Descending |
            Select-Object -First 1 -ExpandProperty FullName
        if ($candidate) {
            return $candidate
        }
    }

    throw 'signtool.exe is required to verify a production installer.'
}

function Invoke-ExternalSigningBoundary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandPath,

        [Parameter(Mandatory = $true)]
        [string]$ArtifactPath
    )

    $global:LASTEXITCODE = 0
    try {
        $signingOutput = @(& $CommandPath -InstallerPath $ArtifactPath 2>&1)
    }
    catch {
        throw 'The external signing boundary failed.'
    }
    if ($LASTEXITCODE -ne 0) {
        throw "The external signing boundary failed with exit code $LASTEXITCODE."
    }

    # The external boundary owns certificate/provider access and RFC 3161
    # timestamping. Its output is deliberately not written to release logs.
    $null = $signingOutput
}

function Get-StableArtifactEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArtifactPath
    )

    $before = Get-Item -LiteralPath $ArtifactPath
    $hash = (Get-FileHash -LiteralPath $ArtifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $after = Get-Item -LiteralPath $ArtifactPath
    if (
        $before.Length -ne $after.Length -or
        $before.LastWriteTimeUtc -ne $after.LastWriteTimeUtc
    ) {
        throw 'The installer changed while final artifact evidence was calculated.'
    }
    if (-not $hash -or $hash -notmatch '^[0-9a-f]{64}$') {
        throw 'The final installer SHA-256 could not be produced.'
    }

    [pscustomobject]@{
        bytes = [int64]$after.Length
        sha256 = $hash
    }
}

function Assert-ApprovedRfc3161Evidence {
    param($Evidence)

    if (
        $null -eq $Evidence -or
        $Evidence.rfc3161_verified -ne $true -or
        [string]$Evidence.message_imprint_digest -ne 'sha256'
    ) {
        throw 'The final installer does not contain approved RFC 3161 timestamp evidence.'
    }
}

function Complete-ReleaseArtifact {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArtifactPath,

        [Parameter(Mandatory = $true)]
        [ValidateSet('Production', 'InternalTestUnsigned')]
        [string]$Mode,

        [string]$ExternalSigningCommand,

        [string]$RequestedSignTool,

        [scriptblock]$SignerInvoker = {
            param($CommandPath, $Installer)
            Invoke-ExternalSigningBoundary -CommandPath $CommandPath -ArtifactPath $Installer
        },

        [scriptblock]$AuthenticodeProbe = {
            param($Installer)
            Get-AuthenticodeSignature -LiteralPath $Installer
        },

        [scriptblock]$NativeVerifier = {
            param($ToolPath, $Installer)
            $verificationOutput = @(& $ToolPath verify /pa /all /v $Installer 2>&1)
            if ($LASTEXITCODE -ne 0) {
                throw "signtool verification failed with exit code $LASTEXITCODE."
            }
            $null = $verificationOutput
        },

        [scriptblock]$Rfc3161Verifier = {
            param($Installer)
            & (Join-Path $PSScriptRoot 'verify-rfc3161-timestamp.ps1') `
                -InstallerPath $Installer
        }
    )

    $artifact = [IO.Path]::GetFullPath($ArtifactPath)
    if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) {
        throw 'The installer to finalize was not found.'
    }

    if ($Mode -eq 'Production') {
        if (-not $ExternalSigningCommand) {
            throw 'Production artifact finalization requires an external signing command.'
        }
        $signer = [IO.Path]::GetFullPath($ExternalSigningCommand)
        if (-not (Test-Path -LiteralPath $signer -PathType Leaf)) {
            throw 'The external signing command was not found.'
        }
        if (Test-PathWithinRoot -Path $signer -Root $ProjectRoot) {
            throw 'The production signing command must remain outside the source repository.'
        }

        & $SignerInvoker $signer $artifact

        $signature = & $AuthenticodeProbe $artifact
        if ([string]$signature.Status -ne 'Valid') {
            throw "The final installer Authenticode status is not Valid: $($signature.Status)."
        }
        if ($null -eq $signature.SignerCertificate) {
            throw 'The final installer does not contain a signer certificate.'
        }
        if ($null -eq $signature.TimeStamperCertificate) {
            throw 'The final installer does not contain a trusted timestamp.'
        }

        $rfc3161Evidence = & $Rfc3161Verifier $artifact
        Assert-ApprovedRfc3161Evidence -Evidence $rfc3161Evidence

        $resolvedSignTool = Resolve-ReleaseSignTool -RequestedPath $RequestedSignTool
        & $NativeVerifier $resolvedSignTool $artifact

        $firstEvidence = Get-StableArtifactEvidence -ArtifactPath $artifact
        $finalSignature = & $AuthenticodeProbe $artifact
        if (
            [string]$finalSignature.Status -ne 'Valid' -or
            $null -eq $finalSignature.SignerCertificate -or
            $null -eq $finalSignature.TimeStamperCertificate
        ) {
            throw 'The final installer signature or timestamp changed during finalization.'
        }
        $finalRfc3161Evidence = & $Rfc3161Verifier $artifact
        Assert-ApprovedRfc3161Evidence -Evidence $finalRfc3161Evidence
        $finalEvidence = Get-StableArtifactEvidence -ArtifactPath $artifact
        if (
            $firstEvidence.bytes -ne $finalEvidence.bytes -or
            $firstEvidence.sha256 -ne $finalEvidence.sha256
        ) {
            throw 'The final installer changed after signature verification.'
        }

        return [pscustomobject]@{
            artifact_class = 'production-signed'
            production_ready = $true
            authenticode_status = 'Valid'
            timestamped = $true
            rfc3161_verified = $true
            timestamp_digest_algorithm = 'sha256'
            signer_subject = [string]$finalSignature.SignerCertificate.Subject
            signer_thumbprint = ([string]$finalSignature.SignerCertificate.Thumbprint).ToLowerInvariant()
            timestamp_subject = [string]$finalSignature.TimeStamperCertificate.Subject
            timestamp_thumbprint = ([string]$finalSignature.TimeStamperCertificate.Thumbprint).ToLowerInvariant()
            installer_bytes = $finalEvidence.bytes
            installer_sha256 = $finalEvidence.sha256
        }
    }

    if ($ExternalSigningCommand) {
        throw 'InternalTestUnsigned mode does not accept a signing command.'
    }
    $unsignedSignature = & $AuthenticodeProbe $artifact
    if (
        [string]$unsignedSignature.Status -eq 'Valid' -or
        $null -ne $unsignedSignature.SignerCertificate
    ) {
        throw 'An unsigned internal-test artifact was unexpectedly Authenticode-signed.'
    }
    $unsignedEvidence = Get-StableArtifactEvidence -ArtifactPath $artifact
    return [pscustomobject]@{
        artifact_class = 'internal-test-unsigned'
        production_ready = $false
        authenticode_status = [string]$unsignedSignature.Status
        timestamped = $false
        rfc3161_verified = $false
        timestamp_digest_algorithm = $null
        signer_subject = $null
        signer_thumbprint = $null
        timestamp_subject = $null
        timestamp_thumbprint = $null
        installer_bytes = $unsignedEvidence.bytes
        installer_sha256 = $unsignedEvidence.sha256
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Complete-ReleaseArtifact `
        -ArtifactPath $InstallerPath `
        -Mode $ArtifactMode `
        -ExternalSigningCommand $SigningCommandPath `
        -RequestedSignTool $SignToolPath
}
