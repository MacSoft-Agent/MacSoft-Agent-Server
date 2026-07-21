import { cn } from '@/lib/utils'

// Compact text mark used where the full wordmark would not fit. Packaging uses
// the supplied raster/ICO assets; this renderer mark stays crisp at every DPI.
export function BrandMark({ className, ...props }: React.ComponentProps<'span'>) {
  return (
    <span
      aria-label="MacSoft Agent"
      className={cn(
        'macsoft-wordmark inline-flex size-14 shrink-0 items-center justify-center rounded-xl border border-[#048FE0]/25 bg-background text-xl font-bold shadow-sm',
        className
      )}
      {...props}
    >
      <span className="text-[#048FE0]">M</span>
      <span className="text-[#FC9421]">S</span>
    </span>
  )
}
