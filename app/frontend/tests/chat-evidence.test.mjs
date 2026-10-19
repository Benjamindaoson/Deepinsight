import test from 'node:test'
import assert from 'node:assert/strict'
import { readEvidencePack, reviewLabel, safeEvidenceUrl, delimitEvidenceLinks, evidenceUrls } from '../src/lib/chat-evidence.ts'

test('offline: publisher changes retain attribution and human gates separately from facts', () => {
  const change = { id: 'publisher-fixture', classification: 'publisher_reported_change', period: '2026Q2', comparison_period: '2026Q1', geography: 'Central London', definition: 'Quarterly take-up', reported_change: '20', change_unit: '%', calculation_performed: false, human_review_status: 'pending_review', evidence: { quote: 'Offline fixture: take-up increased', page: 1, locator: 'pdf:page:1' }, url: 'https://example.org/change.pdf' }
  const pack = readEvidencePack({ publisher_reported_changes: [change] })
  assert.deepEqual(pack.facts, [])
  assert.deepEqual(pack.publisherReportedChanges, [change])
  assert.match(reviewLabel(pack.publisherReportedChanges[0].human_review_status), /Pending review/)
  assert.deepEqual(evidenceUrls(pack), [change.url])
  assert.equal(delimitEvidenceLinks(`${change.url}，待审核`, evidenceUrls(pack)), `<${change.url}>，待审核`)
  assert.deepEqual(readEvidencePack({ facts: [], publisher_reported_changes: [null, {}, { id: 'wrong', classification: 'verified_fact' }] }).publisherReportedChanges, [])
})

test('offline: evidence presentation preserves unknown units, precision, period and review gates', () => {
  const fact = { id: 'fixture', value: '190.00', unit: 'GBP/sqft, time denominator not stated', period: '2026Q2', status: 'needs_review', definition: 'Annual denominator unconfirmed', evidence: { page: 1, locator: 'pdf:page:1', quote: 'Fixture quote' } }
  const pack = readEvidencePack(JSON.stringify({ facts: [fact], documents: { doc: { published_at: null } } }))
  assert.deepEqual(pack.facts[0], fact)
  assert.match(reviewLabel(pack.facts[0].status), /unverified/)
  assert.match(reviewLabel('pending_review'), /Pending review/)
  assert.equal(reviewLabel('rejected'), 'Rejected')
  assert.equal(reviewLabel(undefined), 'Unknown review status')
})
test('offline: malformed tool results and unsafe publisher links are not interpreted as trusted evidence', () => {
  for (const value of ['{broken', null, { facts: 'wrong' }]) assert.equal(readEvidencePack(value), null)
  for (const url of ['javascript:alert(1)', 'data:text/html,hello', '/relative', undefined]) assert.equal(safeEvidenceUrl(url), undefined)
  assert.equal(safeEvidenceUrl('https://example.org/report.pdf'), 'https://example.org/report.pdf')
})

import { explainChatError } from '../src/lib/chat-errors.ts'
test('offline: budget and incomplete output are clear failures, never completion', () => {
  assert.match(explainChatError('TOKEN_BUDGET'), /TOKEN_BUDGET_EXCEEDED/)
  assert.match(explainChatError('RuntimeError'), /did not complete/)
  assert.match(explainChatError('FINAL_ANSWER_MISSING'), /evidence only/)
  assert.match(explainChatError('timed out'), /MODEL_TIMEOUT/)
  assert.match(explainChatError('AbortError'), /STOP_REQUESTED/)
})

test('offline: Chinese punctuation cannot extend a retrieved source URL; unknown URLs remain untouched', () => {
  const url = 'https://example.org/report.pdf'
  assert.equal(delimitEvidenceLinks(`来源（${url}，日期未知）`, [url]), `来源（<${url}>，日期未知）`)
  assert.equal(delimitEvidenceLinks(`[Report](${url})`, [url]), `[Report](${url})`)
  assert.equal(delimitEvidenceLinks('https://unknown.example/a，日期未知', [url]), 'https://unknown.example/a，日期未知')
})
