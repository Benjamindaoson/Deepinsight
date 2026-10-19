import type { ToolCall } from '@/types/os'
import {
  readEvidencePack,
  reviewLabel,
  safeEvidenceUrl
} from '@/lib/chat-evidence'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'

export default function ToolEvidence({ tool }: { tool: ToolCall }) {
  const pack = readEvidencePack(tool.result ?? tool.content)
  const params = useSearchParams()
  return (
    <details className="evidence-pack">
      <summary>
        {tool.tool_name} ·{' '}
        {tool.tool_call_error
          ? 'Tool error'
          : pack
            ? `${pack.facts.length} candidate records${pack.publisherReportedChanges.length ? ` · ${pack.publisherReportedChanges.length} publisher-reported changes` : ''} · view evidence`
            : 'View tool details'}
      </summary>
      {pack ? (
        <>
          <p className="my-3 text-muted">
            {pack.notice ||
              'Source observations retain their original review status.'}
          </p>
          {pack.publisherReportedChanges.length > 0 && (
            <section aria-label="Publisher-reported changes" className="my-3">
              <h3>Publisher-reported changes</h3>
              <p>
                Attributed source statements, not system-calculated changes or
                independently verified facts. Human review status is unchanged.
              </p>
              {pack.publisherReportedChanges.map((change) => (
                <details key={change.id} className="mt-3">
                  <summary>
                    {change.geography} · {change.period} ·{' '}
                    {reviewLabel(change.human_review_status || change.status)}
                  </summary>
                  <p>
                    {change.definition} · Comparison period:{' '}
                    {change.comparison_period || 'Not disclosed'}
                  </p>
                  <p>
                    Reported value: {change.reported_value ?? 'Not disclosed'}{' '}
                    {change.reported_unit} · Reported change:{' '}
                    {change.reported_change ?? 'Not disclosed'}{' '}
                    {change.change_unit}
                  </p>
                  <p>
                    publisher_reported_change · System calculation:{' '}
                    {change.calculation_performed === false
                      ? 'Not performed'
                      : 'Not confirmed'}
                  </p>
                  <p>
                    {change.report_title || change.document_id} · Published:{' '}
                    {change.published_at || 'Not disclosed'}
                  </p>
                  <blockquote>
                    {change.evidence?.quote || 'No source quote supplied'}
                  </blockquote>
                  <p>
                    Page: {change.evidence?.page ?? 'N/A'} ·{' '}
                    {change.evidence?.locator || 'No locator'}
                  </p>
                  <p className="break-all">
                    Record: {change.id}
                    <br />
                    Document: {change.document_id}
                    <br />
                    SHA-256: {change.document_sha256 || 'Not supplied'}
                  </p>
                  <p>{change.limitation}</p>
                  {safeEvidenceUrl(change.url) && (
                    <a
                      href={safeEvidenceUrl(change.url)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Original report ↗
                    </a>
                  )}
                </details>
              ))}
            </section>
          )}
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  {[
                    'Metric / geography',
                    'Period',
                    'Value / unit',
                    'Source',
                    'Review status'
                  ].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pack.facts.map((f) => (
                  <tr key={f.id}>
                    <td>
                      {f.metric}
                      <br />
                      {f.geography}
                    </td>
                    <td>{f.period || 'Not disclosed'}</td>
                    <td>
                      {f.value ?? 'Not disclosed'} {f.unit}
                    </td>
                    <td>
                      {pack.documents[f.document_id || '']?.publisher ||
                        pack.documents[f.document_id || '']?.title ||
                        f.document_id}
                    </td>
                    <td>{reviewLabel(f.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pack.facts.map((f) => {
            const doc = pack.documents[f.document_id || ''] || {}
            const query = new URLSearchParams(params.toString())
            if (f.geography) query.set('geography', f.geography)
            if (f.metric) query.set('metric', f.metric)
            if (f.period) query.set('period', f.period)
            return (
              <details key={f.id} className="mt-3">
                <summary>
                  {f.metric} · {f.geography} · {f.period} — source evidence
                </summary>
                <p className="mt-3">
                  {doc.title || f.document_id} ·{' '}
                  {doc.publisher || 'Publisher not disclosed'} · Published:{' '}
                  {doc.published_at || 'Not disclosed'}
                </p>
                <p>{f.definition}</p>
                <blockquote>
                  {f.evidence?.quote || 'No quote supplied by this tool'}
                </blockquote>
                <p>
                  Page: {f.evidence?.page ?? 'N/A'} ·{' '}
                  {f.evidence?.locator || 'No locator'}
                  <br />
                  Record: {f.id}
                  <br />
                  Document: {f.document_id}
                </p>
                <div className="my-2 flex flex-wrap gap-4">
                  {safeEvidenceUrl(doc.url) && (
                    <a
                      href={safeEvidenceUrl(doc.url)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Original report ↗
                    </a>
                  )}
                  <Link href={`/market-data?${query}`}>View market data</Link>
                </div>
              </details>
            )
          })}
        </>
      ) : (
        <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-all">
          {tool.result ||
            tool.content ||
            (tool.tool_call_error
              ? 'Tool failed; no result was supplied.'
              : 'Tool execution is in progress or has no textual result.')}
        </pre>
      )}
    </details>
  )
}
