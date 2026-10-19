import type { ReportArtifact } from './report-artifact'
export type Citation = {
  fact_id?: string
  id?: string
  title?: string
  url?: string
  source_id?: string
  document_id?: string
  period?: string
}
export type MarketStreamEvent =
  | { type: 'token'; content: string }
  | {
      type: 'progress'
      stage: string
      message: string
      submission_id?: string
      job_id?: string
    }
  | { type: 'report'; report: ReportArtifact; report_id: string }
  | {
      type: 'done'
      citations?: Citation[]
      run_id?: string
      submission_id?: string
      report_id?: string
      research_job_id?: string
      skill_calls?: { skill: string; datasource: string }[]
      as_of?: string | null
      disclaimer?: string
      metrics?: {
        model_requests?: number
        route?: { mode?: 'saved' | 'agent' | 'research' }
      }
    }
  | { type: 'error'; message?: string }

/** Decode SSE across arbitrary byte and CRLF boundaries, including a final un-delimited event. */
export async function readMarketStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: MarketStreamEvent) => void
) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false
  const consume = (block: string) => {
    const payload = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n')
    if (!payload || payload === '[DONE]') return
    const event = JSON.parse(payload) as MarketStreamEvent
    if (event.type === 'done') completed = true
    if (event.type === 'error')
      throw new Error(event.message || 'The native agent reported an error.')
    if (['token', 'done', 'progress', 'report'].includes(event.type))
      onEvent(event)
  }
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer = (buffer + decoder.decode(value, { stream: !done })).replace(
        /\r\n/g,
        '\n'
      )
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        consume(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
      }
      if (done) break
    }
    if (buffer.trim()) consume(buffer)
    if (!completed)
      throw new Error(
        'The stream ended without a completion receipt. Partial text is shown above.'
      )
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
