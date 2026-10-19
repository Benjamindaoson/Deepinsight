'use client'

import { useState, type ReactNode } from 'react'
import Link from 'next/link'
import { MARKET_API, externalUrl } from '@/lib/market-api'
import {
  metricLabels,
  formatReportValue,
  periodLabel,
  reportPresentation
} from '@/lib/report-artifact'
import type {
  ReportArtifact,
  ReportChart,
  ReportFinding
} from '@/lib/report-artifact'
import styles from './institutional-report.module.css'

const statusCopy = {
  success: 'Evidence coverage complete',
  partial: 'Partial research coverage',
  insufficient_evidence: 'Evidence insufficient for confirmed conclusions',
  failed: 'Report generation failed'
}

export default function InstitutionalReport({
  report,
  evidence,
  renderChart
}: {
  report: ReportArtifact
  evidence?: (id: string) => void
  renderChart: (chart: ReportChart) => ReactNode
}) {
  const view = reportPresentation(report)
  const [openEvidence, setOpenEvidence] = useState<string | null>(null)
  const compact = report.report_type === 'fact_answer'
  const index = new Map(report.evidence.map((e, i) => [e.id, i + 1]))
  const sourceGroups = new Map<string, ReportArtifact['evidence']>()
  const relatedGroups = [
    ...new Set((report.related_observations || []).map((f) => f.metric))
  ].map((metric) => {
    const rows = (report.related_observations || []).filter(
      (f) => f.metric === metric
    )
    const leading = rows
      .filter(
        (f, i) =>
          rows.findIndex(
            (other) => other.value === f.value && other.unit === f.unit
          ) === i
      )
      .slice(0, 2)
    return {
      metric,
      leading,
      additional: rows.filter((f) => !leading.includes(f))
    }
  })
  for (const e of report.evidence) {
    const rows = sourceGroups.get(e.document_sha256) || []
    rows.push(e)
    sourceGroups.set(e.document_sha256, rows)
  }
  const publisher = (url?: string) => {
    try {
      const host = new URL(url || '').hostname
      if (host.endsWith('.bnpparibas.co.uk')) return 'BNP Paribas Real Estate'
      if (host === 'jll.com' || host.endsWith('.jll.com')) return 'JLL'
      if (host.endsWith('.savills.co.uk') || host.endsWith('.savills.com'))
        return 'Savills'
      return host || 'Original source'
    } catch {
      return 'Original source'
    }
  }
  const citations = (ids: string[]) =>
    ids
      .filter((id) => index.has(id))
      .map((id) => (
        <a
          key={id}
          href={`#evidence-${id}`}
          className={styles.citation}
          aria-label={`Read source ${index.get(id)}`}
          onClick={() => setOpenEvidence(id)}
        >
          [{index.get(id)}]
        </a>
      ))
  const findings = (title: string, items: ReportFinding[]) =>
    items.length > 0 && (
      <section className={styles.section}>
        <h3>{title}</h3>
        <div className={styles.findings}>
          {items.map((f, i) => (
            <p key={i}>
              <span className={styles.kind}>{f.classification}</span>
              {f.text} {citations(f.evidence_ids)}
            </p>
          ))}
        </div>
      </section>
    )
  const observation = (f: ReportArtifact['market_snapshot'][number]) => (
    <div key={f.fact_id} className={styles.observation}>
      <div>
        <strong>{formatReportValue(f.value)}</strong>{' '}
        {citations(f.evidence_ids)}
      </div>
      <span className={styles.unit}>{f.unit}</span>
      <span className={styles.publisher}>
        {publisher(
          report.evidence.find((e) => e.id === f.evidence_ids[0])?.url
        )}
      </span>
      {f.metric === 'supply' && (
        <span className={styles.unit}>
          {f.definition || 'Supply definition unknown'}
        </span>
      )}
      <span className={styles.recordStatus}>
        {f.review_status === 'approved'
          ? 'Reviewed observation'
          : 'Pending review'}
      </span>
      <details className={styles.definition}>
        <summary>Definition & scope</summary>
        <p>{f.definition || 'Definition not supplied'}</p>
        <p>
          {f.geography} / {periodLabel(f.period)}
        </p>
      </details>
    </div>
  )
  return (
    <article data-report-id={report.report_id} className={styles.report}>
      <header className={styles.cover}>
        <div className={styles.masthead}>
          <strong>DeepInsight Lite</strong>
          <span>Research & advisory intelligence</span>
        </div>
        <div className={styles.coverBody}>
          <div>
            <p className={styles.edition}>
              {periodLabel(report.observation_period)} / London offices
            </p>
            <h2>{report.title}</h2>
            <p className={styles.scope}>{report.geographies.join(' / ')}</p>
            <p className={styles.scope} aria-label="Research scope summary">
              {view.metrics.map((m) => metricLabels[m] || m).join(', ')}
            </p>
          </div>
          <div className={styles.coverNote}>
            <span>Research scope</span>
            <p>{view.metrics.map((m) => metricLabels[m] || m).join(', ')}</p>
            <span>Prepared</span>
            <p>
              {new Date(report.generated_at).toLocaleDateString('en-GB', {
                day: 'numeric',
                month: 'long',
                year: 'numeric',
                timeZone: 'UTC'
              })}
            </p>
          </div>
        </div>
        <nav className={styles.actions} aria-label="Report actions">
          <Link
            href={`/reports?report=${encodeURIComponent(report.report_id)}`}
          >
            Open saved report
          </Link>
          <Link
            href={`/ask?parent_report=${encodeURIComponent(report.report_id)}`}
          >
            Ask a follow-up
          </Link>
          <Link
            href={`/ask?parent_report=${encodeURIComponent(report.report_id)}&action=audit`}
          >
            Audit evidence
          </Link>
          <a
            href={`${MARKET_API}/reports/${encodeURIComponent(report.report_id)}?format=html`}
            target="_blank"
            rel="noreferrer"
          >
            Print / HTML report
          </a>
          <a
            href={`${MARKET_API}/reports/${encodeURIComponent(report.report_id)}?format=markdown`}
          >
            Markdown
          </a>
        </nav>
      </header>

      <aside className={styles.notice} aria-label="Report publication status">
        <strong>{statusCopy[report.generation_status]}</strong>
        <p>
          {report.generation_status === 'insufficient_evidence'
            ? 'The disclosures below are research inputs. Review, source definitions or comparability remain unresolved; a confirmed market view cannot yet be issued.'
            : 'Original disclosures and analytical judgments have separate review requirements. Coverage does not imply approval of an investment conclusion.'}
        </p>
      </aside>

      <section className={styles.brief}>
        <div>
          <h3>{compact ? 'Evidence answer' : 'Executive brief'}</h3>
          <p className={styles.briefLead}>
            {report.key_findings.length
              ? 'Evidence-supported observations'
              : 'A source-led view, with open diligence items'}
          </p>
        </div>
        <div className={styles.briefText}>
          {report.executive_summary.map((f, i) => (
            <p key={i}>
              {f.text} {citations(f.evidence_ids)}
            </p>
          ))}
          <p className={styles.secondary}>
            Read the original definitions alongside each figure. Rental time
            denominators, market boundaries and publisher methods are retained
            as disclosed.
          </p>
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHeading}>
          <h3>Regional evidence</h3>
          <span>{periodLabel(report.observation_period)}</span>
        </div>
        <p className={styles.intro}>
          Source-reported observations. Separate disclosures are retained where
          publishers use different definitions; these figures are not a ranking.
        </p>
        <div
          className={styles.matrixWrap}
          tabIndex={0}
          role="region"
          aria-label="Regional observations table; scroll horizontally for all metrics"
        >
          <table className={styles.matrix}>
            <thead>
              <tr>
                <th scope="col">Submarket</th>
                {view.metrics.map((m) => (
                  <th scope="col" key={m}>
                    {metricLabels[m] || m}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {view.regions.map((region) => (
                <tr key={region.geography}>
                  <th scope="row">{region.geography}</th>
                  {region.cells.map((cell) => (
                    <td key={cell.metric}>
                      {cell.observations.length ? (
                        <>
                          {cell.observations.slice(0, 2).map(observation)}
                          {cell.observations.length > 2 && (
                            <details className={styles.more}>
                              <summary>
                                {cell.observations.length - 2} further source
                                records
                              </summary>
                              {cell.observations.slice(2).map(observation)}
                            </details>
                          )}
                        </>
                      ) : (
                        <span className={styles.missing}>
                          No eligible disclosure
                          <br />
                          <small>Scope or review gap</small>
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className={styles.tableNote}>
          Figures retain original units. A rent quote without an explicit time
          denominator is not annualised. Available stock, construction and
          completions are separate measures.
        </p>
      </section>

      {!!report.related_observations?.length && (
        <section className={styles.context}>
          <h3>Related geography context</h3>
          <p>
            These disclosures cover a combined market. They do not fill Canary
            Wharf-only gaps or participate in regional rankings.
          </p>
          <div className={styles.contextRecords}>
            {relatedGroups.map((group) => (
              <div key={group.metric}>
                <h4>{metricLabels[group.metric] || group.metric}</h4>
                <span>Canary Wharf & Docklands</span>
                {group.leading.map(observation)}
                {!!group.additional.length && (
                  <details className={styles.more}>
                    <summary>
                      {group.additional.length} further source records
                    </summary>
                    {group.additional.map(observation)}
                  </details>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {!compact && (
        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <h3>Market exhibits</h3>
            <span>{view.readyCharts.length} released</span>
          </div>
          {view.readyCharts.length ? (
            <div className={styles.charts}>
              {view.readyCharts.map(renderChart)}
            </div>
          ) : (
            <div className={styles.chartEmpty}>
              <strong>Comparable market charts are not yet available</strong>
              <p>
                There are insufficient compatible, reviewed observations for a
                trend, cross-region chart or supply breakdown. The regional
                evidence table remains available for source-level diligence.
              </p>
            </div>
          )}
          {!!view.unavailableCharts.length && (
            <details className={styles.more}>
              <summary>Why other exhibits are unavailable</summary>
              <ul>
                {view.unavailableCharts.map((c) => (
                  <li key={c.id}>
                    <strong>
                      {metricLabels[c.metric || ''] || 'Market events'} /{' '}
                      {c.type.replaceAll('_', ' ')}:
                    </strong>{' '}
                    {c.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}

      {findings('Key findings', report.key_findings)}
      {report.risks.length > 0 || report.opportunities.length > 0 ? (
        <div className={styles.twoColumn}>
          {findings('Risks', report.risks)}
          {findings('Opportunities', report.opportunities)}
        </div>
      ) : (
        !compact && (
          <section className={styles.section}>
            <h3>Risks & opportunities</h3>
            <p className={styles.intro}>
              No investment judgment is released from the current evidence.
              Source definitions, current-quarter flows and project-level supply
              status need review before assessing downside exposure or an
              actionable opportunity.
            </p>
          </section>
        )
      )}
      {!compact && findings('Outlook & scenarios', report.outlook)}

      <section className={styles.section}>
        <h3>Research coverage & next checks</h3>
        <div className={styles.coverageLine}>
          <strong>
            {view.coveredCells} / {view.totalCells}
          </strong>
          <span>
            requested region–metric cells have source-reported candidates. This
            measures availability, not approval.
          </span>
        </div>
        <div className={styles.gapGrid}>
          {view.gapGroups.map((g) => (
            <div key={g.geography}>
              <h4>{g.geography}</h4>
              <p>
                {g.current.length
                  ? `Review or acquisition needed: ${g.current.map((x) => metricLabels[x.metric] || x.metric).join(', ')}.`
                  : 'Current metric coverage available.'}
              </p>
              {!!g.history.length && (
                <p>
                  Historical comparisons remain unconfirmed for{' '}
                  {g.history.length} requested metrics.
                </p>
              )}
            </div>
          ))}
        </div>
        <details className={styles.more}>
          <summary>Detailed gaps, limitations & generation record</summary>
          <ul>
            {report.data_gaps.map((g, i) => (
              <li key={i}>
                <strong>
                  {g.geography} / {metricLabels[g.metric] || g.metric}
                  {g.component === 'history' ? ' / history' : ''}:
                </strong>{' '}
                {g.reason}
              </li>
            ))}
          </ul>
          <ul>
            {report.limitations.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
          <p>{report.acquisition.notice}</p>
          <p>
            Generated: {report.generated_at}. Publication checks:{' '}
            {report.publication_review.status}. Semantic approval:{' '}
            {report.publication_review.semantic_approval
              ? 'approved'
              : 'pending'}
            .
          </p>
          {report.ai_analysis && (
            <p>
              Model analysis: {report.ai_analysis.status}.{' '}
              {report.ai_analysis.answer}
            </p>
          )}
        </details>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHeading}>
          <h3>Sources & evidence</h3>
          <span>{sourceGroups.size} original documents</span>
        </div>
        <p className={styles.intro}>
          Numbered references link to the saved original quotation. Expand a
          reference to inspect its period, page, collection date and review
          record.
        </p>
        {!report.evidence.length && (
          <p className={styles.missing}>
            No source-verified quotations are available for this scope.
          </p>
        )}
        {[...sourceGroups].map(([hash, records]) => (
          <details
            key={hash}
            className={styles.sourceGroup}
            open={records.some((e) => e.id === openEvidence) || undefined}
          >
            <summary>
              {publisher(records[0].url)} / {periodLabel(records[0].period)}
              <small>
                {records.length} cited observations · expand original quotations
              </small>
            </summary>
            {records.map((e) => (
              <details
                key={e.id}
                id={`evidence-${e.id}`}
                open={openEvidence === e.id || undefined}
                className={styles.source}
              >
                <summary>
                  <span className={styles.sourceNumber}>{index.get(e.id)}</span>
                  <span>
                    {e.report_title || 'Original report'}
                    <small>
                      {periodLabel(e.period)}
                      {e.page ? ` / page ${e.page}` : ''} /{' '}
                      {e.review_status === 'approved'
                        ? 'Reviewed'
                        : 'Pending review'}
                    </small>
                  </span>
                </summary>
                <blockquote>{e.quote}</blockquote>
                <dl className={styles.sourceMeta}>
                  <div>
                    <dt>Review actor</dt>
                    <dd>{e.reviewed_by || 'Not recorded'}</dd>
                  </div>
                  {e.review_note && (
                    <div>
                      <dt>Review basis</dt>
                      <dd>{e.review_note}</dd>
                    </div>
                  )}
                  <div>
                    <dt>Publication</dt>
                    <dd>{e.published_at || 'Not supplied'}</dd>
                  </div>
                  <div>
                    <dt>Collected</dt>
                    <dd>{e.collected_at || 'Not supplied'}</dd>
                  </div>
                  <div>
                    <dt>Source last checked</dt>
                    <dd>{e.source_last_checked_at || 'Unknown'}</dd>
                  </div>
                  <div>
                    <dt>Evidence integrity checked at</dt>
                    <dd>
                      {e.evidence_integrity_checked_at || 'Unknown'} /{' '}
                      {e.evidence_integrity_status || 'Unknown'}
                    </dd>
                  </div>
                  <div>
                    <dt>Locator</dt>
                    <dd>{e.locator || 'Not supplied'}</dd>
                  </div>
                  <div>
                    <dt>Original SHA-256</dt>
                    <dd>{e.document_sha256}</dd>
                  </div>
                </dl>
                <div className={styles.sourceActions}>
                  {externalUrl(e.url) && (
                    <a
                      href={externalUrl(e.url)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Read original source
                    </a>
                  )}
                  {e.fact_id &&
                    (evidence ? (
                      <button onClick={() => evidence(e.fact_id!)}>
                        Open evidence viewer
                      </button>
                    ) : (
                      <Link
                        href={`/market-data?evidence=${encodeURIComponent(e.fact_id)}`}
                      >
                        Open evidence viewer
                      </Link>
                    ))}
                </div>
              </details>
            ))}
          </details>
        ))}
      </section>
      <footer className={styles.footer}>
        <span>DeepInsight Lite / Research evidence record</span>
        <span>{report.report_id.slice(0, 8)}</span>
      </footer>
    </article>
  )
}
