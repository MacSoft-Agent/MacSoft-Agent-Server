import type { MacSoftProductMetadata } from './macsoft-product'
import {
  acceptMacSoftUpdate,
  MacSoftUpdateError,
  type TrustedMacSoftRelease,
  verifyMacSoftUpdateManifest
} from './macsoft-update-manifest'

export const INSTALLER_UPDATE_MESSAGE = 'Updates are installed using a MacSoft Agent installer.'

interface CustomerUpdateCheckDependencies {
  fetchManifest: (url: string) => Promise<string>
  now?: () => number
  onTrustedRelease?: (release: TrustedMacSoftRelease | null) => void
  packaged: boolean
}

type CustomerUpdateMetadata = Pick<
  MacSoftProductMetadata,
  'build_id' | 'channel' | 'product' | 'product_version' | 'update_manifest_public_key' | 'update_manifest_url'
>

export async function customerUpdateCheck(
  metadata: CustomerUpdateMetadata,
  dependencies?: CustomerUpdateCheckDependencies
) {
  const fetchedAt = dependencies?.now?.() ?? Date.now()
  dependencies?.onTrustedRelease?.(null)
  if (!metadata.update_manifest_url || !metadata.update_manifest_public_key) {
    return {
      supported: false,
      updateAvailable: false,
      error: 'update-not-configured',
      message: 'Trusted MacSoft Agent updates are not configured for this build.',
      fetchedAt,
      manifestConfigured: false
    }
  }
  if (!dependencies?.packaged) {
    return {
      supported: false,
      updateAvailable: false,
      error: 'packaged-only',
      message: 'Installer-managed updates are available only in an installed MacSoft Agent build.',
      fetchedAt,
      manifestConfigured: true
    }
  }
  try {
    const manifest = await dependencies.fetchManifest(metadata.update_manifest_url)
    const verified = verifyMacSoftUpdateManifest(manifest, metadata.update_manifest_public_key)
    const release = acceptMacSoftUpdate(verified, {
      channel: metadata.channel,
      product: metadata.product,
      version: metadata.product_version
    })
    dependencies.onTrustedRelease?.(release)
    return {
      supported: true,
      updateAvailable: true,
      message: `MacSoft Agent ${release.version} is available.`,
      fetchedAt,
      manifestConfigured: true,
      currentVersion: metadata.product_version,
      currentBuildId: metadata.build_id,
      targetVersion: release.version,
      targetBuildId: release.buildId,
      publishedAt: release.publishedAt
    }
  } catch (error) {
    if (error instanceof MacSoftUpdateError && error.code === 'release-same-version') {
      return {
        supported: true,
        updateAvailable: false,
        message: 'MacSoft Agent is up to date.',
        fetchedAt,
        manifestConfigured: true,
        currentVersion: metadata.product_version,
        currentBuildId: metadata.build_id
      }
    }
    const code = error instanceof MacSoftUpdateError ? error.code : 'update-check-failed'
    const message =
      error instanceof MacSoftUpdateError
        ? error.message
        : 'MacSoft Agent could not retrieve a trusted update manifest.'
    return {
      supported: false,
      updateAvailable: false,
      error: code,
      message,
      fetchedAt,
      manifestConfigured: true
    }
  }
}

export function customerUpdateApply() {
  return { ok: false, error: 'installer-managed', message: INSTALLER_UPDATE_MESSAGE }
}

export function customerUpdateBranch() {
  return { branch: 'installer-managed' }
}
