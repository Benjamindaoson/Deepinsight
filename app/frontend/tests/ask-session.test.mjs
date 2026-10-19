import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { readMarketStream } from '../src/lib/market-stream.ts'

// Execute the real AskPage submit handler at its network boundary. Keeping the
// component's JSX out of this harness avoids substituting its child components.
const path = new URL('../src/components/market/MarketApp.tsx', import.meta.url)
const source = ts.createSourceFile('MarketApp.tsx', readFileSync(path, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
const page = source.statements.find((node) => ts.isFunctionDeclaration(node) && node.name?.text === 'AskPage')
const send = page.body.statements.flatMap((node) => ts.isVariableStatement(node) ? [...node.declarationList.declarations] : []).find((node) => node.name.getText(source) === 'send')
const handler = ts.transpileModule(`const send = ${send.initializer.getText(source)};`, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS }
}).outputText
const createSend = new Function('context', `
  const { question, entries, sessionId, guard, controller, runtimeMode, mode,
    setStreaming, setEntries, setQuestion, refreshSources, params, fetch,
    MARKET_API, readMarketStream } = context;
  ${handler}
  return send;
`)

function conversation() {
  return { sessionId: { current: null }, guard: { current: false }, controller: { current: null } }
}

async function submit(state, message, requests) {
  let entries = [{ report: { report_id: 'stored-parent-report' } }]
  const send = createSend({
    ...state, question: message, entries, runtimeMode: 'live', mode: 'agent',
    setStreaming() {}, setQuestion() {}, setEntries(update) { entries = update(entries) },
    refreshSources: false, params: new URLSearchParams(), MARKET_API: 'http://127.0.0.1/api/market',
    readMarketStream,
    async fetch(url, options) {
      assert.equal(url, 'http://127.0.0.1/api/market/ask')
      requests.push(JSON.parse(options.body))
      return new Response('data: {"type":"done"}\n\n')
    }
  })
  await send({ preventDefault() {} })
}

test('AskPage sends one stable session for follow-ups and a fresh session for a new mounted conversation', async () => {
  const requests = []
  const first = conversation()
  await submit(first, 'Initial report question', requests)
  await submit(first, 'Explain the previous report', requests)
  await submit(conversation(), 'New conversation question', requests)
  assert.equal(requests.length, 3)
  assert.match(requests[0].session_id || '', /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i)
  assert.equal(requests[1].session_id, requests[0].session_id)
  assert.notEqual(requests[2].session_id, requests[0].session_id)
  assert.deepEqual(requests.map((request) => request.parent_report_id), Array(3).fill('stored-parent-report'))
})
