import assert from 'node:assert/strict'
import { test } from 'node:test'

import { resolveMacSoftPromptCapabilities } from './use-macsoft-desktop-chat-status'

test('MacSoft readiness controls editing independently from submission', () => {
  assert.deepEqual(resolveMacSoftPromptCapabilities(true, 'ready', false), {
    canEditPrompt: true,
    canSubmitPrompt: false
  })
  assert.deepEqual(resolveMacSoftPromptCapabilities(true, 'unavailable', true), {
    canEditPrompt: false,
    canSubmitPrompt: false
  })
})

test('upstream Hermes behavior still follows native Gateway readiness', () => {
  assert.deepEqual(resolveMacSoftPromptCapabilities(false, 'idle', true), {
    canEditPrompt: true,
    canSubmitPrompt: true
  })
  assert.deepEqual(resolveMacSoftPromptCapabilities(false, 'ready', false), {
    canEditPrompt: false,
    canSubmitPrompt: false
  })
})
