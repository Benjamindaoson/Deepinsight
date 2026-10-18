'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useMarket } from '@/hooks/useMarket'
import {
  type Evidence,
  type List,
  type MarketEvent,
  type Report,
  MARKET_API
} from '@/lib/market-api'
import {
  researchQuestion,
  resolveResearchRecord,
  reviewMeaning,
  type ResearchKind
} from '@/lib/workflow'

export default function ResearchContext({
  onDraft,
  onReady,
  streaming
}: {
  onDraft: (draft: string, evidence?: string) => void
  onReady: (readyKey: string | null) => void
  streaming: boolean
}) {
  const params = useSearchParams()
  const kind = params.get('context')
  const id = params.get('record') || ''
  const valid = ['fact', 'event', 'report'].includes(kind || '') && Boolean(id)
  const path = valid
    ? kind === 'fact'
      ? `/facts/${encodeURIComponent(id)}/evidence`
      : kind === 'event'
        ? '/events'
        : '/reports'
    : null
  const state = useMarket<Evidence | List<MarketEvent | Report>>(path)
  const applied = useRef('')
  const [retry, setRetry] = useState(0)
  const [reportText, setReportText] = useState<{
    id: string
    text: string
    error: string
  } | null>(null)
  useEffect(() => {
    if (kind !== 'report' || !valid) return
    const controller = new AbortController()
    setReportText(null)
    void fetch(
      `${MARKET_API}/reports/${encodeURIComponent(id)}?format=markdown`,
      { signal: controller.signal }
    )
      .then(async (response) => {
        if (!response.ok)
          throw new Error('The report body could not be loaded.')
        const text = await response.text()
        if (!controller.signal.aborted)
          setReportText({ id, text: text.slice(0, 8000), error: '' })
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setReportText({
            id,
            text: '',
            error: error instanceof Error ? error.message : 'Report unavailable'
          })
      })
    return () => controller.abort()
  }, [kind, id, valid, retry])
  const row = useMemo(() => {
    const record = resolveResearchRecord(kind || '', id, state.data)
    if (!record) return null
    if (kind === 'fact') {
      const evidence = state.data as Evidence
      return {
        ...record,
        evidence: evidence.evidence,
        url: evidence.document.url,
        published_at: evidence.document.published_at,
        collected_at: evidence.document.collected_at,
        publisher: record.publisher || evidence.document.title
      }
    }
    return kind === 'report'
      ? {
          ...record,
          summary:
            reportText?.id === id
              ? `Saved report excerpt (up to 8,000 characters; read the complete report for all evidence):\n${reportText.text}`
              : undefined
        }
      : record
  }, [kind, id, state.data, reportText])
  useEffect(() => {
    onReady(
      valid &&
        row &&
        !state.loading &&
        !state.error &&
        (kind !== 'report' || (reportText?.id === id && !reportText.error))
        ? `${kind}:${id}`
        : null
    )
  }, [valid, row, state.loading, state.error, kind, id, reportText, onReady])
  useEffect(() => {
    if (!kind && applied.current) {
      applied.current = ''
      onDraft('')
      return
    }
    const key = `${kind}:${id}`
    if (
      !row ||
      streaming ||
      params.get('session') ||
      applied.current === key ||
      (kind === 'report' &&
        (!reportText || reportText.id !== id || reportText.error))
    )
      return
    applied.current = key
    const payload = researchQuestion(kind as ResearchKind, row)
    onDraft(
      `${payload.split('\n\n')[0]} ${row.title || [row.geography, row.metric, row.period].filter(Boolean).join(' · ')}`,
      payload
    )
  }, [kind, id, row, onDraft, streaming, params, reportText])
  if (!kind) return null
  const loading = state.loading || (kind === 'report' && reportText?.id !== id)
  const error =
    state.error ||
    (kind === 'report' && reportText?.id === id ? reportText.error : '')
  return (
    <section
      className="research-context"
      aria-label="Selected research context"
    >
      <p className="font-semibold">
        Continue from{' '}
        {kind === 'fact'
          ? 'a saved observation'
          : kind === 'event'
            ? 'a reported event'
            : 'a saved report'}
      </p>
      {!valid ? (
        <p role="alert">
          This research link is incomplete. Open the original record to start
          again.
        </p>
      ) : loading ? (
        <p role="status">Loading the selected record and its evidence…</p>
      ) : error || !row ? (
        <div role="alert">
          <p>
            The selected record could not be loaded. No analysis has been
            started.
          </p>
          <button
            className="underline"
            onClick={() => {
              setRetry((value) => value + 1)
              void state.reload()
            }}
          >
            Reload context
          </button>
          {error && (
            <details>
              <summary>Technical details</summary>
              {error}
            </details>
          )}
        </div>
      ) : (
        <>
          <p>
            {row.title || `${row.metric} · ${row.geography}`} ·{' '}
            {kind === 'report'
              ? `${row.period} briefing; statistical coverage dates not supplied`
              : row.period || 'Reporting period not supplied'}
          </p>
          <p>
            {reviewMeaning(
              kind === 'report' ? undefined : row.status,
              row.human_review_status
            )}
          </p>
          <p>
            A question is ready to edit. The selected evidence will be included
            when you send it to the AI service.
          </p>
          <details>
            <summary>Selected evidence details</summary>
            <p>Record: {row.id}</p>
            <p>{row.evidence?.quote || row.summary}</p>
          </details>
          <Link
            className="underline"
            href={
              kind === 'report'
                ? `/reports?report=${encodeURIComponent(id)}`
                : kind === 'event'
                  ? `/events?event=${encodeURIComponent(id)}`
                  : `/market-data?evidence=${encodeURIComponent(id)}`
            }
          >
            Return to original record
          </Link>
        </>
      )}
      {params.get('session') && (
        <p>
          Start a new conversation before using this context. The current
          conversation has been preserved.
        </p>
      )}
      {streaming && (
        <p>
          Finish or stop the current response before starting this research.
        </p>
      )}
    </section>
  )
}
