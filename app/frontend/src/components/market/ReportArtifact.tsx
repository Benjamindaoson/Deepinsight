'use client'

import { useEffect, useState } from 'react'
import { MARKET_API } from '@/lib/market-api'
import type { ReportArtifact, ReportChart } from '@/lib/report-artifact'
import { chartNumbers } from '@/lib/report-artifact'
import InstitutionalReport from './InstitutionalReport'

const muted = 'text-xs text-slate-500 dark:text-slate-400'
const frame =
  'rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900'

function Chart({ chart }: { chart: ReportChart }) {
  const values = chartNumbers(chart)
  const usable =
    chart.status === 'ready' && (chart.type === 'event_timeline' || values)
  const max = values ? Math.max(1, ...values.map(Math.abs)) : 1
  const min = values ? Math.min(0, ...values) : 0
  const range = max - min || 1
  const xy = (v: number, i: number) =>
    `${55 + (i * 420) / Math.max(1, (values?.length || 1) - 1)},${165 - ((v - min) / range) * 125}`
  return (
    <figure className={frame}>
      <figcaption className="text-sm font-semibold">{chart.title}</figcaption>
      <p className={`${muted} mt-1`}>
        {chart.unit ||
          (chart.type === 'event_timeline'
            ? 'Dated events'
            : 'Unit unavailable')}{' '}
        · {chart.geographies.join(' / ')} ·{' '}
        {chart.observation_period || 'Period unknown'}
      </p>
      {!usable ? (
        <p
          role={chart.status === 'error' ? 'alert' : 'status'}
          className="mt-4 text-sm text-slate-500"
        >
          {chart.reason || 'Chart data is unavailable.'}
        </p>
      ) : chart.type === 'event_timeline' ? (
        <ol className="mt-4 space-y-3 border-l-2 border-teal-600 pl-4">
          {chart.points.map((p, i) => (
            <li key={i}>
              <time className={muted}>{p.date}</time>
              <p className="text-sm">{p.label}</p>
              <p className={muted}>
                {p.category} · {p.geography}
              </p>
            </li>
          ))}
        </ol>
      ) : chart.type === 'time_series' && values ? (
        <svg
          viewBox="0 0 540 220"
          role="img"
          aria-label={`${chart.title}. ${chart.points.map((p) => `${p.label}: ${p.value} ${chart.unit}`).join('; ')}`}
          className="mt-3 w-full"
        >
          <line
            x1="55"
            y1="165"
            x2="500"
            y2="165"
            stroke="currentColor"
            opacity=".3"
          />
          <text x="5" y="43" fill="currentColor" fontSize="12">
            {max}
          </text>
          <text x="5" y="168" fill="currentColor" fontSize="12">
            {min}
          </text>
          <polyline
            points={values.map(xy).join(' ')}
            fill="none"
            stroke="#0f766e"
            strokeWidth="3"
          />
          {values.map((v, i) => {
            const [x, y] = xy(v, i).split(',')
            return (
              <g key={i}>
                <circle cx={x} cy={y} r="5" fill="#0f766e" />
                <text
                  x={x}
                  y={Number(y) - 12}
                  textAnchor="middle"
                  fill="currentColor"
                  fontSize="12"
                >
                  {v}
                </text>
                <text
                  x={x}
                  y="192"
                  textAnchor="middle"
                  fill="currentColor"
                  fontSize="12"
                >
                  {chart.points[i].label}
                </text>
              </g>
            )
          })}
        </svg>
      ) : values ? (
        <div className="mt-4 space-y-3">
          {chart.points.map((p, i) => (
            <div key={i}>
              <div className="flex justify-between gap-3 text-xs">
                <span>{p.label}</span>
                <span>
                  {p.value} {chart.unit}
                </span>
              </div>
              <div className="mt-1 h-3 rounded bg-slate-100 dark:bg-slate-800">
                <div
                  className="h-3 rounded bg-teal-700"
                  style={{ width: `${(Math.max(0, values[i]) / max) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {usable && (
        <details className="mt-4 text-xs">
          <summary className="cursor-pointer font-medium text-teal-700 dark:text-teal-300">
            View chart data & source records
          </summary>
          <div className="mt-2 overflow-auto">
            <table className="w-full text-left">
              <thead>
                <tr>
                  <th>Observation</th>
                  <th>Original / computed value</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {chart.points.map((p, i) => (
                  <tr key={i}>
                    <td className="p-2">
                      {p.label} {p.date}
                    </td>
                    <td>
                      {p.value ?? 'Event'} {chart.unit}
                    </td>
                    <td>
                      {p.evidence_ids.map((id) => (
                        <a
                          className="mr-2 underline"
                          key={id}
                          href={`#evidence-${id}`}
                        >
                          Source
                        </a>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </figure>
  )
}

export function ReportView({
  report,
  evidence
}: {
  report: ReportArtifact
  evidence?: (id: string) => void
}) {
  return (
    <InstitutionalReport
      report={report}
      evidence={evidence}
      renderChart={(chart) => <Chart key={chart.id} chart={chart} />}
    />
  )
}

export default function SavedReport({ reportId }: { reportId: string }) {
  const [report, setReport] = useState<ReportArtifact | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setReport(null)
    setError('')
    fetch(`${MARKET_API}/reports/${encodeURIComponent(reportId)}?format=json`, {
      cache: 'no-store',
      signal: controller.signal
    })
      .then(async (response) => {
        if (!response.ok)
          throw new Error(`Report unavailable (${response.status}).`)
        return response.json()
      })
      .then((data) => {
        if (data.schema_version !== '1.0')
          throw new Error('Unsupported report schema.')
        setReport(data)
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message)
      })
    return () => controller.abort()
  }, [reportId, attempt])
  if (error)
    return (
      <div role="alert" className={frame}>
        {error}{' '}
        <button className="underline" onClick={() => setAttempt((a) => a + 1)}>
          Retry reading saved report
        </button>
      </div>
    )
  return report ? (
    <ReportView report={report} />
  ) : (
    <p role="status" className={frame}>
      Loading source-verified report…
    </p>
  )
}
