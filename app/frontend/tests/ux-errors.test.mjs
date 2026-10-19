import test from 'node:test'
import assert from 'node:assert/strict'
import {
  chatFailureCopy,
  explainChatError,
  restoredRunError
} from '../src/lib/chat-errors.ts'

test('offline: errors explain distinct user recovery, never invent a successful answer', () => {
  assert.match(chatFailureCopy('Failed to fetch'), /connection/i)
  assert.match(chatFailureCopy('401 API key missing'), /configuration/i)
  assert.match(chatFailureCopy('MODEL_TIMEOUT'), /time/i)
  assert.match(chatFailureCopy('503 service unavailable'), /unavailable/i)
  assert.match(chatFailureCopy('No usable sources'), /sources/i)
  assert.match(chatFailureCopy('STOP_REQUESTED'), /stopped/i)
  assert.match(chatFailureCopy('TOKEN_BUDGET_EXCEEDED'), /context|budget/i)
})

test('offline: provider usage overruns are distinguished from local estimates', () => {
  assert.match(
    chatFailureCopy('PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED'),
    /provider.*usage/i
  )
  assert.match(
    explainChatError('PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED'),
    /reported usage exceeded/i
  )
  assert.match(
    explainChatError('PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED'),
    /No automatic retry/
  )
  assert.match(explainChatError('PROVIDER_USAGE_MISSING'), /usage receipt/i)
})

test('offline: restoring failed native history never promotes its saved draft', () => {
  assert.match(
    restoredRunError({
      status: 'ERROR',
      events: [
        { event: 'RunError', content: 'PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED' }
      ]
    }),
    /reported usage exceeded/
  )
  assert.match(restoredRunError({ status: 'ERROR' }), /FINAL_ANSWER_MISSING/)
  assert.match(
    restoredRunError({ status: 'CANCELLED' }),
    /without a complete final answer/
  )
  assert.equal(restoredRunError({ status: 'COMPLETED' }), '')
})

test('quota exhaustion is actionable and does not imply a model answer', () => {
  for (const raw of ['PROVIDER_QUOTA_EXHAUSTED', 'insufficient_user_quota', '账户余额或套餐额度不足']) {
    assert.match(chatFailureCopy(raw), /balance or plan quota is exhausted/)
    assert.match(explainChatError(raw), /PROVIDER_QUOTA_EXHAUSTED/)
    assert.match(explainChatError(raw), /no automatic retry/i)
  }
})
