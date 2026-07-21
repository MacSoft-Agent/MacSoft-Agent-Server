import { cn } from '@/lib/utils'

export function MacSoftWordmark({ className, ...props }: React.ComponentProps<'span'>) {
  return (
    <span
      aria-label="MacSoft Agent"
      className={cn('macsoft-wordmark inline-block whitespace-nowrap', className)}
      {...props}
    >
      <span className="text-[#048FE0]">Mac</span>
      <span className="text-[#FC9421]">Soft</span>
      <span className="text-[#048FE0]"> Agent</span>
    </span>
  )
}
