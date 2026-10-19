import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createSelectionGuard,
  retryableJob,
  jobPresentation,
  researchLink,
  researchQuestion,
  resolveResearchRecord,
  reviewMeaning,
  attachResearchContext,
  splitResearchInput
} from '../src/lib/workflow.ts'
import { conversationLink, contextIsReady } from '../src/lib/workflow.ts'
import { formatConversationTime } from '../src/lib/workflow.ts'
import { latestChatFailure } from '../src/lib/workflow.ts'

test('partial research retains a link to its saved evidence report without claiming success', () => {
  const view = jobPresentation({ kind: 'research', status: 'partial', result: { report_id: 'partial-report' } })
  assert.equal(view.href, '/reports?report=partial-report')
  assert.match(view.explanation, /Inspect the result/)
  assert.equal(view.showProgress, false)
})

test('history: same selection can be retried, older success/error is rejected, live run cannot be overwritten', () => {
  const guard = createSelectionGuard()
  const first = guard.begin('a')
  const retry = guard.begin('a')
  assert.equal(guard.current(first, 'a', false), false)
  assert.equal(guard.current(retry, 'a', false), true)
  assert.equal(guard.current(retry, 'a', true), false)
  assert.equal(guard.current(retry, null, false), false)
  const later = guard.begin('b')
  assert.equal(guard.current(retry, 'a', false), false)
  assert.equal(guard.current(later, 'b', false), true)
})

test('job retry matches backend contract, including interrupted and partial but excluding model jobs', () => {
  for (const kind of ['refresh', 'extract', 'research'])
    for (const status of ['failed', 'interrupted', 'partial'])
      assert.equal(retryableJob({ kind, status }), true)
  for (const kind of ['ask', 'report', 'report_analysis'])
    assert.equal(retryableJob({ kind, status: 'failed' }), false)
  assert.equal(retryableJob({ kind: 'refresh', status: 'cancelled' }), false)
  assert.equal(retryableJob({ kind: 'extract', status: 'succeeded' }), false)
  assert.equal(jobPresentation({ kind: 'research', status: 'succeeded', result: { report_id: 'saved-1' } }).href,
    '/reports?report=saved-1')
})

test('terminal processing never implies approved evidence or a successful 100% failure', () => {
  const failed = jobPresentation({
    kind: 'extract',
    status: 'failed',
    progress: 100
  })
  assert.equal(failed.showProgress, false)
  assert.match(failed.explanation, /not completed|failed/i)
  assert.equal(
    jobPresentation({ kind: 'refresh', status: 'partial', progress: 100 })
      .showProgress,
    false
  )
  assert.equal(
    jobPresentation({ kind: 'ask', status: 'running' }).progress,
    undefined
  )
  const report = jobPresentation({
    kind: 'report',
    status: 'succeeded',
    result: { report_id: 'a/b' }
  })
  assert.equal(report.href, '/reports?report=a%2Fb')
  assert.match(report.explanation, /review/i)
})

test('research identity is encoded and resolved from actual records, never from fabricated query labels', () => {
  assert.equal(researchLink('fact', 'a/b'), '/?context=fact&record=a%2Fb')
  const fact = {
    id: 'f1',
    metric: 'rent',
    geography: 'West End',
    period: '2026Q2',
    value: '190.00',
    unit: 'GBP/sqft, time denominator not stated',
    status: 'needs_review',
    evidence: { quote: 'Exact quoted amount' }
  }
  assert.equal(resolveResearchRecord('fact', 'f1', { fact }).id, 'f1')
  assert.equal(resolveResearchRecord('fact', 'different', { fact }), null)
  assert.equal(resolveResearchRecord('event', 'missing', { items: [] }), null)
  const draft = researchQuestion('fact', fact)
  for (const term of [
    'f1',
    'West End',
    '2026Q2',
    '190.00',
    'needs_review',
    'Exact quoted amount'
  ])
    assert.ok(draft.includes(term), term)
  assert.match(draft, /Do not infer|Do not calculate/)
  assert.doesNotMatch(draft, /per annum|verified fact/)
})

test('report/event handoffs retain real identity and explicit unknown dates', () => {
  const event = {
    id: 'e1',
    title: 'Original event',
    summary: 'Source statement',
    status: 'pending_review',
    url: 'https://example.org/event'
  }
  assert.equal(resolveResearchRecord('event', 'e1', { items: [event] }), event)
  assert.match(researchQuestion('event', event), /Original event/)
  assert.match(researchQuestion('event', event), /Not supplied/)
  assert.match(
    researchQuestion('report', {
      id: 'r1',
      title: 'Saved report',
      period: 'weekly'
    }),
    /r1/
  )
  assert.match(reviewMeaning('needs_review'), /cannot|not eligible/i)
  assert.match(reviewMeaning('unknown'), /not confirmed/i)
})

test('context travels with a human-editable question and remains available in restored native input', () => {
  const input = attachResearchContext(
    'My edited question',
    'Exact saved quote; pending_review; f1'
  )
  assert.deepEqual(splitResearchInput(input), {
    question: 'My edited question',
    context: 'Exact saved quote; pending_review; f1'
  })
  assert.deepEqual(splitResearchInput('Ordinary question'), {
    question: 'Ordinary question',
    context: ''
  })
  assert.equal(
    attachResearchContext('Ordinary question', ''),
    'Ordinary question'
  )
})

test('history navigation drops prior research scope and a later record cannot reuse readiness', () => {
  const href = conversationLink(
    'agent=a&db_id=db&context=fact&record=old&report=r&session=old',
    'new'
  )
  assert.equal(href, '/?agent=a&db_id=db&session=new')
  assert.equal(contextIsReady('fact', 'new', 'fact:old'), false)
  assert.equal(contextIsReady('fact', 'new', 'fact:new'), true)
  assert.equal(contextIsReady(null, null, 'fact:old'), false)
})

test('machine validation cannot be represented as human approval', () => {
  assert.match(
    reviewMeaning('validated', 'pending_review'),
    /awaiting.*human|human.*pending/i
  )
  assert.doesNotMatch(
    reviewMeaning('validated'),
    /This observation is reviewed/
  )
  assert.match(reviewMeaning('validated', 'approved'), /human.reviewed/i)
  const draft = researchQuestion('fact', {
    id: 'v1',
    status: 'validated',
    human_review_status: 'pending_review'
  })
  assert.match(draft, /"human_review_status": "pending_review"/)
  assert.match(draft, /"machine_validation_status": "validated"/)
})

test('native history dates support actual ISO timestamps, epoch seconds, milliseconds and unknowns', () => {
  for (const value of ['2026-10-18T02:47:34+00:00', 1792291654, 1792291654000])
    assert.doesNotMatch(formatConversationTime(value), /Invalid|not supplied/)
  assert.equal(formatConversationTime(undefined), 'Time not supplied')
  assert.equal(formatConversationTime('bad date'), 'Time not supplied')
  const url = researchLink(
    'event',
    'e1',
    'agent=actual-agent&db_id=actual-db&session=old&context=fact&record=old'
  )
  assert.match(url, /agent=actual-agent/)
  assert.match(url, /db_id=actual-db/)
  assert.doesNotMatch(url, /session=old|record=old/)
})

test('restored final errors offer recovery without reviving an older failed response', () => {
  assert.equal(
    latestChatFailure([
      { role: 'agent', streamingError: true, errorMessage: 'real failure' }
    ]),
    'real failure'
  )
  assert.equal(
    latestChatFailure([{ role: 'agent', streamingError: true }]),
    'FINAL_ANSWER_MISSING'
  )
  assert.equal(
    latestChatFailure([
      { role: 'agent', streamingError: true },
      { role: 'agent', streamingError: false }
    ]),
    ''
  )
})
