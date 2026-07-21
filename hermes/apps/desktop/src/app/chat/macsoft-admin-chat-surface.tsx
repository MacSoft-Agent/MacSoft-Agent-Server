import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { cn } from '@/lib/utils'

import type { useMacSoftAdminChat } from './hooks/use-macsoft-admin-chat'

type AdminChatController = ReturnType<typeof useMacSoftAdminChat>

export function MacSoftAdminChatSurface({
  controller,
  onCreate,
  onDelete,
  onSelect
}: {
  controller: AdminChatController
  onCreate: () => void
  onDelete: (sessionId: string) => void
  onSelect: (sessionId: string) => void
}) {
  const { activity, error, historyLoading, messages, selectedSessionId, sessions, streaming } = controller

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex shrink-0 items-center gap-2 border-b border-border/60 px-4 py-2">
        <select
          aria-label="Admin chat session"
          className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none"
          disabled={streaming || sessions.length === 0}
          onChange={event => onSelect(event.target.value)}
          value={selectedSessionId ?? ''}
        >
          {sessions.map(session => (
            <option key={session.session_id} value={session.session_id}>
              {session.title || 'Admin Chat'}
            </option>
          ))}
        </select>
        <Button aria-label="Create Admin session" disabled={streaming} onClick={onCreate} size="icon-xs" variant="ghost">
          <Codicon name="add" />
        </Button>
        <Button
          aria-label="Delete Admin session"
          disabled={streaming || !selectedSessionId}
          onClick={() => selectedSessionId && onDelete(selectedSessionId)}
          size="icon-xs"
          variant="ghost"
        >
          <Codicon name="trash" />
        </Button>
      </div>
      <div aria-live="polite" className="min-h-0 flex-1 overflow-y-auto px-5 py-6">
        {historyLoading && <div className="text-sm text-muted-foreground">Loading Admin chat history...</div>}
        {!historyLoading && messages.length === 0 && (
          <div className="grid h-full place-items-center text-sm text-muted-foreground">Start a Server Admin chat.</div>
        )}
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {messages.map(message => (
            <div
              className={cn(
                'max-w-[85%] whitespace-pre-wrap break-words text-sm leading-relaxed',
                message.role === 'user' ? 'self-end rounded-xl bg-primary/10 px-3 py-2 text-foreground' : 'self-start text-foreground'
              )}
              key={message.id}
            >
              {message.content}
            </div>
          ))}
          {activity && <div className="text-xs text-muted-foreground">{activity.title}</div>}
          {error && <div className="text-sm text-destructive">{error}</div>}
        </div>
      </div>
    </div>
  )
}
