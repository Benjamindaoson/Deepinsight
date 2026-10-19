'use client'

import { useMarket } from '@/hooks/useMarket'

type Coverage = {
  notice: string
  metrics: {
    id: string
    name: string
    status: string
    fact_ids: string[]
    event_ids: string[]
    source_geographies: string[]
    approved_fact_count: number
    source_errors: { source_id: string; reason?: string; health: string }[]
    limitations?: string
  }[]
}

export default function IndicatorCoverage() {
  const { data, loading, error, reload } = useMarket<Coverage>('/coverage')
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 text-sm">
      <div className="flex items-center justify-between gap-4">
        <h2 className="font-semibold">Assessment coverage · 20 indicators</h2>
        <button
          type="button"
          className="text-teal-800 underline"
          onClick={() => void reload()}
        >
          Reload coverage
        </button>
      </div>
      <p className="my-3 text-slate-600">
        {data?.notice ||
          'Source access, candidate evidence and approval are separate checks.'}
      </p>
      {loading && <p>Loading indicator evidence…</p>}
      {error && <p role="alert">{error}</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <caption className="sr-only">
            Actual evidence coverage for all 20 assessment indicators
          </caption>
          <thead>
            <tr className="border-b">
              <th className="p-2">Indicator</th>
              <th className="p-2">Evidence</th>
              <th className="p-2">Coverage and blockers</th>
            </tr>
          </thead>
          <tbody>
            {data?.metrics.map((m) => (
              <tr key={m.id} className="border-b align-top">
                <th scope="row" className="p-2 font-medium">
                  {m.id} · {m.name}
                </th>
                <td className="p-2">
                  {m.status}
                  <br />
                  {m.fact_ids.length} numeric · {m.event_ids.length} qualitative
                  <br />
                  {m.approved_fact_count} approved
                </td>
                <td className="p-2">
                  <p>
                    {m.source_geographies.join('; ') ||
                      'No numerical geographic series'}
                  </p>
                  <details className="mt-1">
                    <summary>Limitations and source access</summary>
                    <p className="mt-1">{m.limitations}</p>
                    {m.source_errors.map((e) => (
                      <p key={e.source_id}>
                        {e.source_id}: {e.reason || e.health}
                      </p>
                    ))}
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
