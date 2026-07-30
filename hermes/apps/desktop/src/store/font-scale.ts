import { Codecs, persistentAtom } from '@/lib/persisted'

export const FONT_SCALE_OPTIONS = [
  { id: 'small', label: 'Small', percent: 100, scale: 1 },
  { id: 'normal', label: 'Normal', percent: 112, scale: 1.12 },
  { id: 'large', label: 'Large', percent: 125, scale: 1.25 },
  { id: 'extra_large', label: 'Extra Large', percent: 137, scale: 1.37 },
  { id: 'senior', label: 'Senior', percent: 150, scale: 1.5 }
] as const

export type FontScale = (typeof FONT_SCALE_OPTIONS)[number]['id']

export const DEFAULT_FONT_SCALE: FontScale = 'large'
export const FONT_SCALE_STORAGE_KEY = 'macsoft.server.desktop.fontScale.v1'

export function normalizeFontScale(value: unknown): FontScale {
  return FONT_SCALE_OPTIONS.some(option => option.id === value) ? (value as FontScale) : DEFAULT_FONT_SCALE
}

export function fontScaleOption(value: unknown) {
  const normalized = normalizeFontScale(value)
  return FONT_SCALE_OPTIONS.find(option => option.id === normalized)!
}

export function applyFontScale(value: unknown): FontScale {
  const option = fontScaleOption(value)

  if (typeof document !== 'undefined') {
    document.documentElement.style.setProperty('--macsoft-font-scale', String(option.scale))
    document.documentElement.style.setProperty('--macsoft-font-scale-percent', `${option.percent}%`)
    document.documentElement.dataset.macsoftFontScale = option.id
  }

  return option.id
}

export const $fontScale = persistentAtom<FontScale>(
  FONT_SCALE_STORAGE_KEY,
  DEFAULT_FONT_SCALE,
  {
    decode: raw => normalizeFontScale(Codecs.text.decode(raw)),
    encode: value => normalizeFontScale(value)
  }
)

export function setFontScale(value: unknown): void {
  $fontScale.set(normalizeFontScale(value))
}

$fontScale.subscribe(value => applyFontScale(value))
