import type { MacSoftProductMetadata } from './macsoft-product'

export const INSTALLER_UPDATE_MESSAGE = 'Updates are installed using a MacSoft Agent installer.'

export function customerUpdateCheck(metadata: Pick<MacSoftProductMetadata, 'update_manifest_url'>) {
  return {
    supported: false,
    error: 'installer-managed',
    message: INSTALLER_UPDATE_MESSAGE,
    fetchedAt: Date.now(),
    manifestConfigured: Boolean(metadata.update_manifest_url)
  }
}

export function customerUpdateApply() {
  return { ok: false, error: 'installer-managed', message: INSTALLER_UPDATE_MESSAGE }
}

export function customerUpdateBranch() {
  return { branch: 'installer-managed' }
}
