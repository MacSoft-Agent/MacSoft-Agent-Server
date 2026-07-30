[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath
)

$ErrorActionPreference = 'Stop'
$Rfc3161CounterSignatureOid = '1.3.6.1.4.1.311.3.3.1'
$LegacyCounterSignatureOid = '1.2.840.113549.1.9.6'
$NestedAuthenticodeSignatureOid = '1.3.6.1.4.1.311.2.4.1'
$Sha256Oid = '2.16.840.1.101.3.4.2.1'

function Get-EmbeddedAuthenticodeSignature {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 64 -or $bytes[0] -ne 0x4d -or $bytes[1] -ne 0x5a) {
        throw 'The installer is not a valid PE image.'
    }

    $peOffset = [BitConverter]::ToInt32($bytes, 0x3c)
    if (
        $peOffset -lt 0 -or
        $peOffset + 24 -gt $bytes.Length -or
        $bytes[$peOffset] -ne 0x50 -or
        $bytes[$peOffset + 1] -ne 0x45 -or
        $bytes[$peOffset + 2] -ne 0 -or
        $bytes[$peOffset + 3] -ne 0
    ) {
        throw 'The installer PE header is invalid.'
    }

    $optionalHeaderOffset = $peOffset + 24
    $optionalMagic = [BitConverter]::ToUInt16($bytes, $optionalHeaderOffset)
    if ($optionalMagic -eq 0x10b) {
        $dataDirectoryOffset = $optionalHeaderOffset + 96
    }
    elseif ($optionalMagic -eq 0x20b) {
        $dataDirectoryOffset = $optionalHeaderOffset + 112
    }
    else {
        throw 'The installer PE optional header is unsupported.'
    }

    $securityDirectoryOffset = $dataDirectoryOffset + (4 * 8)
    if ($securityDirectoryOffset + 8 -gt $bytes.Length) {
        throw 'The installer PE security directory is missing.'
    }
    $certificateTableOffset = [BitConverter]::ToUInt32($bytes, $securityDirectoryOffset)
    $certificateTableSize = [BitConverter]::ToUInt32($bytes, $securityDirectoryOffset + 4)
    if (
        $certificateTableOffset -eq 0 -or
        $certificateTableSize -lt 8 -or
        [uint64]$certificateTableOffset + [uint64]$certificateTableSize -gt [uint64]$bytes.Length
    ) {
        throw 'The installer does not contain an embedded Authenticode signature.'
    }

    $signatures = @()
    $cursor = [uint64]$certificateTableOffset
    $tableEnd = [uint64]$certificateTableOffset + [uint64]$certificateTableSize
    while ($cursor + 8 -le $tableEnd) {
        $entryOffset = [int]$cursor
        $entryLength = [BitConverter]::ToUInt32($bytes, $entryOffset)
        if ($entryLength -lt 8 -or $cursor + $entryLength -gt $tableEnd) {
            throw 'The installer Authenticode certificate table is malformed.'
        }
        $revision = [BitConverter]::ToUInt16($bytes, $entryOffset + 4)
        $certificateType = [BitConverter]::ToUInt16($bytes, $entryOffset + 6)
        if ($certificateType -eq 0x0002) {
            if ($revision -ne 0x0200) {
                throw 'The installer Authenticode certificate revision is unsupported.'
            }
            $signature = New-Object byte[] ($entryLength - 8)
            [Array]::Copy($bytes, $entryOffset + 8, $signature, 0, $signature.Length)
            $signatures += ,$signature
        }
        $cursor += (($entryLength + 7) -band (-bnot 7))
    }

    if ($signatures.Count -ne 1) {
        throw 'The installer must contain exactly one embedded PKCS#7 Authenticode signature.'
    }
    return $signatures[0]
}

function Initialize-Rfc3161NativeVerifier {
    if ('MacSoft.Release.Rfc3161Native' -as [type]) {
        return
    }

    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace MacSoft.Release
{
    [StructLayout(LayoutKind.Sequential)]
    public struct CryptDataBlob
    {
        public uint Size;
        public IntPtr Data;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct CryptAlgorithmIdentifier
    {
        public IntPtr ObjectId;
        public CryptDataBlob Parameters;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct CryptTimestampInfo
    {
        public uint Version;
        public IntPtr TsaPolicyId;
        public CryptAlgorithmIdentifier HashAlgorithm;
        public CryptDataBlob HashedMessage;
        public CryptDataBlob SerialNumber;
        public System.Runtime.InteropServices.ComTypes.FILETIME Time;
        public IntPtr Accuracy;
        [MarshalAs(UnmanagedType.Bool)]
        public bool Ordering;
        public CryptDataBlob Nonce;
        public CryptDataBlob Tsa;
        public uint ExtensionCount;
        public IntPtr Extensions;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct CryptTimestampContext
    {
        public uint EncodedSize;
        public IntPtr Encoded;
        public IntPtr TimestampInfo;
    }

    public static class Rfc3161Native
    {
        [DllImport("crypt32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CryptVerifyTimeStampSignature(
            byte[] timestampContentInfo,
            uint timestampContentInfoSize,
            byte[] signedData,
            uint signedDataSize,
            IntPtr additionalStore,
            out IntPtr timestampContext,
            out IntPtr timestampSigner,
            out IntPtr store
        );

        [DllImport("crypt32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CryptMemFree(IntPtr buffer);

        [DllImport("crypt32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CertFreeCertificateContext(IntPtr certificateContext);

        [DllImport("crypt32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CertCloseStore(IntPtr certificateStore, uint flags);

        public static string Verify(byte[] timestampContentInfo, byte[] signedData)
        {
            IntPtr timestampContext = IntPtr.Zero;
            IntPtr timestampSigner = IntPtr.Zero;
            IntPtr store = IntPtr.Zero;
            try
            {
                if (!CryptVerifyTimeStampSignature(
                    timestampContentInfo,
                    checked((uint)timestampContentInfo.Length),
                    signedData,
                    checked((uint)signedData.Length),
                    IntPtr.Zero,
                    out timestampContext,
                    out timestampSigner,
                    out store))
                {
                    throw new System.ComponentModel.Win32Exception(
                        Marshal.GetLastWin32Error(),
                        "Windows could not verify the RFC 3161 timestamp token and message imprint."
                    );
                }
                if (timestampContext == IntPtr.Zero || timestampSigner == IntPtr.Zero)
                {
                    throw new InvalidOperationException(
                        "Windows returned incomplete RFC 3161 verification evidence."
                    );
                }
                CryptTimestampContext context =
                    (CryptTimestampContext)Marshal.PtrToStructure(
                        timestampContext,
                        typeof(CryptTimestampContext)
                    );
                if (context.TimestampInfo == IntPtr.Zero)
                {
                    throw new InvalidOperationException(
                        "Windows returned no decoded RFC 3161 timestamp information."
                    );
                }
                CryptTimestampInfo info =
                    (CryptTimestampInfo)Marshal.PtrToStructure(
                        context.TimestampInfo,
                        typeof(CryptTimestampInfo)
                    );
                string objectId = Marshal.PtrToStringAnsi(info.HashAlgorithm.ObjectId);
                if (String.IsNullOrWhiteSpace(objectId))
                {
                    throw new InvalidOperationException(
                        "Windows returned no RFC 3161 message-imprint digest algorithm."
                    );
                }
                return objectId;
            }
            finally
            {
                if (timestampSigner != IntPtr.Zero)
                {
                    CertFreeCertificateContext(timestampSigner);
                }
                if (store != IntPtr.Zero)
                {
                    CertCloseStore(store, 0);
                }
                if (timestampContext != IntPtr.Zero)
                {
                    CryptMemFree(timestampContext);
                }
            }
        }
    }
}
'@
}

function Read-AuthenticodeTimestampAttributes {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    Add-Type -AssemblyName System.Security
    $encodedSignature = Get-EmbeddedAuthenticodeSignature -Path $Path
    $cms = New-Object System.Security.Cryptography.Pkcs.SignedCms
    try {
        $cms.Decode($encodedSignature)
    }
    catch {
        throw 'The installer Authenticode PKCS#7 signature is malformed.'
    }
    if ($cms.SignerInfos.Count -ne 1) {
        throw 'The installer Authenticode signature must contain exactly one primary signer.'
    }

    $signer = $cms.SignerInfos[0]
    $rfc3161Attributes = @(
        $signer.UnsignedAttributes |
            Where-Object { $_.Oid.Value -eq $Rfc3161CounterSignatureOid }
    )
    $legacyAttributes = @(
        $signer.UnsignedAttributes |
            Where-Object { $_.Oid.Value -eq $LegacyCounterSignatureOid }
    )
    $nestedSignatureAttributes = @(
        $signer.UnsignedAttributes |
            Where-Object { $_.Oid.Value -eq $NestedAuthenticodeSignatureOid }
    )

    [pscustomobject]@{
        rfc3161_attribute_count = $rfc3161Attributes.Count
        legacy_attribute_count = $legacyAttributes.Count
        nested_signature_attribute_count = $nestedSignatureAttributes.Count
        rfc3161_value_count = if ($rfc3161Attributes.Count -eq 1) {
            $rfc3161Attributes[0].Values.Count
        }
        else {
            0
        }
        timestamp_content_info = if (
            $rfc3161Attributes.Count -eq 1 -and
            $rfc3161Attributes[0].Values.Count -eq 1
        ) {
            $rfc3161Attributes[0].Values[0].RawData
        }
        else {
            $null
        }
        signed_data = $signer.GetSignature()
    }
}

function Get-Rfc3161TimestampEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [scriptblock]$CmsEvidenceReader = {
            param($Installer)
            Read-AuthenticodeTimestampAttributes -Path $Installer
        },

        [scriptblock]$NativeVerifier = {
            param($TimestampContentInfo, $SignedData)
            Initialize-Rfc3161NativeVerifier
            [MacSoft.Release.Rfc3161Native]::Verify($TimestampContentInfo, $SignedData)
        }
    )

    $cmsEvidence = & $CmsEvidenceReader $Path
    if ($null -eq $cmsEvidence) {
        throw 'The installer RFC 3161 timestamp evidence could not be read.'
    }
    if ([int]$cmsEvidence.nested_signature_attribute_count -gt 0) {
        throw 'The installer contains an unsupported nested Authenticode signature.'
    }
    if ([int]$cmsEvidence.rfc3161_attribute_count -eq 0) {
        if ([int]$cmsEvidence.legacy_attribute_count -gt 0) {
            throw 'The installer contains only a legacy Authenticode timestamp.'
        }
        throw 'The installer does not contain an RFC 3161 timestamp.'
    }
    if ([int]$cmsEvidence.legacy_attribute_count -gt 0) {
        throw 'The installer contains an ambiguous legacy and RFC 3161 timestamp combination.'
    }
    if (
        [int]$cmsEvidence.rfc3161_attribute_count -ne 1 -or
        [int]$cmsEvidence.rfc3161_value_count -ne 1
    ) {
        throw 'The installer RFC 3161 timestamp evidence is malformed or ambiguous.'
    }

    [byte[]]$timestampContentInfo = $cmsEvidence.timestamp_content_info
    [byte[]]$signedData = $cmsEvidence.signed_data
    if (
        $null -eq $timestampContentInfo -or
        $null -eq $signedData -or
        $timestampContentInfo.Length -eq 0 -or
        $signedData.Length -eq 0
    ) {
        throw 'The installer RFC 3161 timestamp evidence is incomplete.'
    }

    try {
        $digestOid = & $NativeVerifier $timestampContentInfo $signedData
    }
    catch {
        throw "RFC 3161 timestamp verification failed: $($_.Exception.Message)"
    }
    if ([string]$digestOid -ne $Sha256Oid) {
        throw "The RFC 3161 message-imprint digest is not approved: $digestOid."
    }

    [pscustomobject]@{
        rfc3161_verified = $true
        message_imprint_digest = 'sha256'
        message_imprint_digest_oid = $Sha256Oid
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Get-Rfc3161TimestampEvidence -Path ([IO.Path]::GetFullPath($InstallerPath))
}
