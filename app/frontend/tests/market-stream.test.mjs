import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readMarketStream} from '../src/lib/market-stream.ts'

function stream(text, bytewise = false) {
  const bytes = new TextEncoder().encode(text)
  return new ReadableStream({start(controller) {
    if (bytewise) for (const byte of bytes) controller.enqueue(Uint8Array.of(byte))
    else controller.enqueue(bytes)
    controller.close()
  }})
}

test('retains UTF-8 tokens, CRLF split over bytes, and native run/citation receipt', async () => {
  const events = []
  await readMarketStream(stream(': heartbeat\r\n\r\ndata: {"type":"token","content":"£25 — London"}\r\n\r\ndata: {"type":"done","run_id":"native-123","citations":[{"fact_id":"source-fact"}]}', true), event => events.push(event))
  assert.equal(events[0].content, '£25 — London')
  assert.equal(events[1].run_id, 'native-123')
  assert.equal(events[1].citations[0].fact_id, 'source-fact')
})

test('does not represent interrupted partial output as a completed answer', async () => {
  const tokens = []
  await assert.rejects(readMarketStream(stream('data: {"type":"token","content":"Partial"}\n\n'), event => tokens.push(event)), /without a completion receipt/)
  assert.equal(tokens[0].content, 'Partial')
})

test('surfaces actual provider errors even after partial output', async () => {
  await assert.rejects(readMarketStream(stream('data: {"type":"token","content":"Partial"}\n\ndata: {"type":"error","message":"Provider balance unavailable"}\n\n'), () => {}), /Provider balance unavailable/)
})

test('passes the explicit budget explanation to the page without a completion event', async () => {
  const events = []
  const message = 'TOKEN_BUDGET: stopped before the next model request. The conservative context estimate plus usage would exceed the unchanged 60,000 input / 8,000 output Token budget. No automatic retry.'
  await assert.rejects(readMarketStream(stream('data: ' + JSON.stringify({type: 'error', code: 'TOKEN_BUDGET', message}) + '\n\n', true), event => events.push(event)), error => error.message === message)
  assert.equal(events.length, 0)
})
