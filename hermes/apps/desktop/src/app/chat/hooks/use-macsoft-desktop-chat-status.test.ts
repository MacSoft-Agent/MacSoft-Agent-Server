import { expect, test } from 'vitest'

import { resolveMacSoftPromptCapabilities } from './use-macsoft-desktop-chat-status'

test('MacSoft readiness controls editing independently from submission', () => {
  expect(resolveMacSoftPromptCapabilities(true, 'ready', false)).toEqual({
    canEditPrompt: true,
    canSubmitPrompt: false
  })
  expect(resolveMacSoftPromptCapabilities(true, 'unavailable', true)).toEqual({
    canEditPrompt: false,
    canSubmitPrompt: false
  })
})

test('upstream Hermes behavior still follows native Gateway readiness', () => {
  expect(resolveMacSoftPromptCapabilities(false, 'idle', true)).toEqual({
    canEditPrompt: true,
    canSubmitPrompt: true
  })
  expect(resolveMacSoftPromptCapabilities(false, 'ready', false)).toEqual({
    canEditPrompt: false,
    canSubmitPrompt: false
  })
})
