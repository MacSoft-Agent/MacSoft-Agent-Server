import { useStore } from '@nanostores/react'
import { useEffect } from 'react'

import { BrandMark } from '@/components/brand-mark'
import { RefreshCw } from '@/lib/icons'
import { $desktopVersion, refreshDesktopVersion } from '@/store/updates'

import { SectionHeading, SettingsContent } from './primitives'

export function AboutSettings() {
  const version = useStore($desktopVersion)

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
        </div>
      </div>

      <div className="mx-auto mt-4 w-full max-w-2xl">
        <SectionHeading icon={RefreshCw} title="Updates" />
        <div className="rounded-xl border border-border/70 bg-muted/20 px-4 py-3 text-sm text-foreground">
          <p className="font-medium">Updates are installed using a MacSoft Agent installer.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            This build does not contact or modify a source repository.
          </p>
        </div>
      </div>
    </SettingsContent>
  )
}
