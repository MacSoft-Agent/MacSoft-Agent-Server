import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

const GLOBAL_TRAINING_HELP_SEEN_KEY = 'macsoft.global-training-help-seen.v1'

function hasSeenGlobalTrainingHelp() {
  try {
    return window.localStorage.getItem(GLOBAL_TRAINING_HELP_SEEN_KEY) === '1'
  } catch {
    return false
  }
}

function rememberGlobalTrainingHelp() {
  try {
    window.localStorage.setItem(GLOBAL_TRAINING_HELP_SEEN_KEY, '1')
  } catch {
    // Help remains available when localStorage is unavailable.
  }
}

export function GlobalTrainingHelp({ entrySignal }: { entrySignal: number }) {
  const [open, setOpen] = useState(false)
  const previousEntrySignal = useRef(entrySignal)

  useEffect(() => {
    if (entrySignal === previousEntrySignal.current) return
    previousEntrySignal.current = entrySignal
    if (hasSeenGlobalTrainingHelp()) return

    rememberGlobalTrainingHelp()
    setOpen(true)
  }, [entrySignal])

  return (
    <Popover onOpenChange={setOpen} open={open}>
      <PopoverTrigger asChild>
        <Button
          aria-label="About Global Training"
          className="size-5 rounded-full border border-(--ui-stroke-secondary) p-0 text-[0.6875rem]"
          size="icon-xs"
          type="button"
          variant="ghost"
        >
          <Codicon name="question" size={12} />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-3" side="right">
        <div className="space-y-2 text-xs leading-5 text-(--ui-text-secondary)">
          <div>
            <h3 className="text-[0.8125rem] font-semibold text-foreground">What is Global Training?</h3>
            <p>It creates reusable improvements that can be inherited by every Client.</p>
          </div>
          <ol className="list-decimal space-y-1 pl-4">
            <li>Open a General or Targeted Workflow training session.</li>
            <li>Choose Enable Training before sending a training message.</li>
            <li>Review the generated Proposal. Nothing changes globally until an administrator approves it.</li>
          </ol>
          <p>
            General classifies the relevant Workflow. Targeted can improve only the Workflow selected when the session
            was created.
          </p>
          <p className="font-medium text-amber-700 dark:text-amber-200">
            Do not include personal or customer-private information, credentials, or single-user preferences.
          </p>
          <p>Ordinary Server chats and Client chats do not train the global environment.</p>
        </div>
      </PopoverContent>
    </Popover>
  )
}
