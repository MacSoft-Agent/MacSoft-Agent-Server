import { beforeEach, describe, expect, it } from 'vitest'

import {
  applyFontScale,
  DEFAULT_FONT_SCALE,
  FONT_SCALE_STORAGE_KEY,
  normalizeFontScale,
  setFontScale
} from './font-scale'

describe('Server Desktop font scale', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.style.removeProperty('--macsoft-font-scale')
    document.documentElement.style.removeProperty('--macsoft-font-scale-percent')
    delete document.documentElement.dataset.macsoftFontScale
  })

  it('falls back safely when a persisted value is invalid', () => {
    expect(normalizeFontScale('unknown')).toBe(DEFAULT_FONT_SCALE)
    expect(normalizeFontScale(null)).toBe(DEFAULT_FONT_SCALE)
  })

  it('applies the selected scale to the document', () => {
    expect(applyFontScale('senior')).toBe('senior')
    expect(document.documentElement.style.getPropertyValue('--macsoft-font-scale')).toBe('1.5')
    expect(document.documentElement.style.getPropertyValue('--macsoft-font-scale-percent')).toBe('150%')
    expect(document.documentElement.dataset.macsoftFontScale).toBe('senior')
  })

  it('persists the selection for the next Desktop launch', () => {
    setFontScale('small')
    expect(localStorage.getItem(FONT_SCALE_STORAGE_KEY)).toBe('small')
  })
})
