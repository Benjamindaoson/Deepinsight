import test from 'node:test'
import assert from 'node:assert/strict'
import { getPublication, publicationLabel } from '../src/lib/publication.ts'

test('fallback and limited-check labels never imply semantic approval', () => {
  assert.match(publicationLabel('deterministic_evidence_fallback'), /AI 草稿已拦截/)
  assert.match(publicationLabel('ai_limited_checks'), /不代表语义或人工审核通过/)
})

test('publication is one read-only request; errors never resubmit a Run', async () => {
  const original = globalThis.fetch
  const calls = []
  globalThis.fetch = async (...args) => {
    calls.push(args)
    return { ok: false, status: 422 }
  }
  try {
    await assert.rejects(getPublication('http://localhost:7780', 'session', 'run'), /原始草稿未展示/)
    assert.equal(calls.length, 1)
    assert.equal(calls[0][1].method, undefined)
    assert.equal(calls[0][0], 'http://localhost:7780/api/market/sessions/session/runs/run/publication')
  } finally { globalThis.fetch = original }
})

test('valid fallback returned, empty or unknown publication rejected', async () => {
  const original = globalThis.fetch
  try {
    for (const value of [{answer: ''}, {answer:'unsafe',answer_origin:'raw'}]) {
      globalThis.fetch = async () => ({ok:true,json:async()=>value})
      await assert.rejects(getPublication('http://localhost:7780','s','r'), /不完整/)
    }
    globalThis.fetch = async () => ({ok:true,json:async()=>({answer:'Evidence only',answer_origin:'deterministic_evidence_fallback'})})
    assert.equal((await getPublication('http://localhost:7780','s','r')).answer, 'Evidence only')
  } finally { globalThis.fetch = original }
})
