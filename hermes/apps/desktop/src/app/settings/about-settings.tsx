import { useStore } from '@nanostores/react'
import { useEffect, useState } from 'react'

import { BrandMark } from '@/components/brand-mark'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { RefreshCw } from '@/lib/icons'
import {
  $desktopVersion,
  $updateApply,
  $updateChecking,
  $updateStatus,
  applyUpdates,
  checkUpdates,
  refreshDesktopVersion,
  setUpdateOverlayOpen
} from '@/store/updates'

import { SectionHeading, SettingsContent } from './primitives'

export function AboutSettings() {
  const version = useStore($desktopVersion)
  const apply = useStore($updateApply)
  const checking = useStore($updateChecking)
  const update = useStore($updateStatus)
  const [confirmUpdate, setConfirmUpdate] = useState(false)
  const updating = apply.applying || apply.stage === 'restart'

  useEffect(() => {
    void refreshDesktopVersion()
  }, [])

  return (
    <SettingsContent>
      <div className="flex flex-col items-center gap-3 pt-6 pb-2 text-center">
        <BrandMark className="size-16" />
        <div>
          <h2 className="text-lg font-semibold tracking-tight">MacSoft Agent</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {version?.appVersion ? `Version ${version.appVersion}` : 'Version unavailable'}
          </p>
          {version?.buildId ? (
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              Build {version.buildId} · {version.channel}
            </p>
          ) : null}
        </div>
      </div>

      <div className="mx-auto mt-4 w-full max-w-2xl">
        <SectionHeading icon={RefreshCw} title="Updates" />
        <div className="rounded-xl border border-border/70 bg-muted/20 px-4 py-3 text-sm text-foreground">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-medium">
                {update?.updateAvailable
                  ? `MacSoft Agent ${update.targetVersion ?? 'update'} is available`
                  : 'MacSoft Agent updates'}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {updating
                  ? apply.message || 'Downloading update…'
                  : update?.message ??
                  'Check the trusted MacSoft release source for a newer installed version.'}
              </p>
              {update?.targetBuildId ? (
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Target build {update.targetBuildId}
                </p>
              ) : null}
            </div>
            <div className="flex shrink-0 gap-2">
              <Button
                disabled={checking || updating}
                onClick={() => void checkUpdates()}
                type="button"
                variant="outline"
              >
                <RefreshCw className={checking ? 'animate-spin' : undefined} />
                {checking ? 'Checking…' : 'Check for updates'}
              </Button>
              {update?.updateAvailable ? (
                <Button disabled={updating} onClick={() => setConfirmUpdate(true)} type="button">
                  {updating ? 'Downloading…' : 'Install update'}
                </Button>
              ) : null}
            </div>
          </div>
          <p className="mt-3 border-t border-border/50 pt-2 text-[11px] text-muted-foreground">
            Updates use a signed manifest and a Windows installer. Source code and Git are not modified.
          </p>
        </div>
      </div>

      <ConfirmDialog
        busyLabel="Preparing update…"
        confirmLabel="Download and install"
        description={
          <>
            MacSoft Agent will verify the installer, ask for Windows administrator approval, preserve
            ProgramData, and restart its services. If installation health checks fail, the previous
            program files will be restored.
          </>
        }
        dismissOnConfirm
        onClose={() => setConfirmUpdate(false)}
        onConfirm={() => {
          setUpdateOverlayOpen(true)
          void applyUpdates()
        }}
        open={confirmUpdate}
        title={`Install MacSoft Agent ${update?.targetVersion ?? 'update'}?`}
      />
    </SettingsContent>
  )
}
