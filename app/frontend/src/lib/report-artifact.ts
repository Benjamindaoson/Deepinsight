export type ReportFinding = {
  text: string
  classification: 'fact' | 'calculation' | 'inference' | 'scenario'
  evidence_ids: string[]
}
export type ReportPoint = {
  label: string
  value?: string | null
  fact_id?: string | null
  evidence_ids: string[]
  geography?: string | null
  period?: string | null
  date?: string | null
  category?: string | null
}
export type ReportChart = {
  id: string
  type:
    | 'time_series'
    | 'regional_comparison'
    | 'supply_structure'
    | 'event_timeline'
  title: string
  metric?: string | null
  unit?: string | null
  geographies: string[]
  observation_period: string | null
  status: 'ready' | 'unavailable' | 'error'
  reason?: string | null
  points: ReportPoint[]
}
export type ReportEvidence = {
  id: string
  fact_id?: string | null
  document_id: string
  report_title: string
  quote: string
  url: string
  period: string | null
  page: number | null
  locator: string | null
  published_at: string | null
  collected_at: string | null
  source_last_checked_at?: string | null
  reviewed_by?: string | null
  review_note?: string | null
  reviewed_at?: string | null
  evidence_integrity_checked_at?: string | null
  evidence_integrity_status?: string
  document_sha256: string
  source_document_sha256?: string
  receipt_sha256?: string | null
  provenance_kind?: string | null
  review_status: string
}
export type ReportArtifact = {
  schema_version: '1.0'
  report_id: string
  title: string
  report_type: 'fact_answer' | 'topic_analysis' | 'market_report'
  generated_at: string
  query: string
  scope?: { metrics: string[] }
  geographies: string[]
  observation_period: string | null
  generation_status: 'success' | 'partial' | 'insufficient_evidence' | 'failed'
  executive_summary: ReportFinding[]
  key_findings: ReportFinding[]
  risks: ReportFinding[]
  opportunities: ReportFinding[]
  outlook: ReportFinding[]
  charts: ReportChart[]
  market_snapshot: {
    fact_id: string
    geography: string
    metric: string
    period: string
    value: string
    unit: string
    definition: string | null
    review_status: string
    evidence_ids: string[]
  }[]
  related_observations?: ReportArtifact['market_snapshot']
  sources?: { document_id: string; title: string; url: string }[]
  regional_comparison: {
    geography: string
    metric: string
    period: string | null
    fact_ids: string[]
    status: string
  }[]
  data_gaps: {
    geography: string
    metric: string
    period: string | null
    reason: string
    component?: string
  }[]
  limitations: string[]
  evidence: ReportEvidence[]
  publication_review: {
    status: string
    codes: string[]
    semantic_approval: boolean
  }
  acquisition: {
    mode: string
    notice: string
    status?: string
    job_id?: string
  }
  ai_analysis?: { status: string; answer?: string } | null
}

/** Native tool results survive session replay. Ignore arbitrary model prose. */
export function reportIdFromTools(
  tools: {
    tool_name?: string
    result?: unknown
    content?: unknown
    tool_call_error?: boolean
  }[] = []
) {
  for (const tool of tools) {
    if (tool.tool_name !== 'search_market_evidence' || tool.tool_call_error)
      continue
    try {
      const raw = tool.result ?? tool.content
      const pack = typeof raw === 'string' ? JSON.parse(raw) : raw
      if (pack && typeof pack.report_id === 'string')
        return pack.report_id as string
    } catch {
      /* A malformed tool result cannot select an artifact. */
    }
  }
  return undefined
}

export function chartNumbers(chart: ReportChart) {
  const values = chart.points.map((point) => Number(point.value))
  return values.length > 0 &&
    chart.points.every(
      (p) => p.value !== null && p.value !== undefined && p.value !== ''
    ) &&
    values.every(Number.isFinite)
    ? values
    : null
}

export const metricLabels: Record<string, string> = {
  rent: 'Prime / office rent',
  vacancy: 'Vacancy',
  availability: 'Available area',
  takeup: 'Leasing take-up',
  supply: 'Supply / pipeline',
  prelet: 'Pre-let area'
}

export function periodLabel(period: string | null) {
  return (
    period?.replace(/^(20\d{2})Q([1-4])$/, 'Q$2 $1') || 'Period unconfirmed'
  )
}

export function formatReportValue(value: string) {
  if (!/^-?\d+(?:\.\d+)?$/.test(value)) return value
  const [integer, decimal] = value.split('.')
  return (
    integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',') +
    (decimal === undefined ? '' : '.' + decimal)
  )
}

/** Presentation only: retains every disclosure; never equates combined regions or ranks candidates. */
export function reportPresentation(report: ReportArtifact) {
  const distinctFirst = (rows: ReportArtifact['market_snapshot']) => {
    const seen = new Set<string>()
    const first: typeof rows = [],
      rest: typeof rows = []
    for (const row of rows) {
      const key = row.value
      if (seen.has(key)) rest.push(row)
      else {
        seen.add(key)
        first.push(row)
      }
    }
    return [...first, ...rest]
  }
  const metrics = report.scope?.metrics || [
    ...new Set(report.regional_comparison.map((r) => r.metric))
  ]
  const regions = report.geographies.map((geography) => ({
    geography,
    cells: metrics.map((metric) => ({
      metric,
      observations: distinctFirst(
        report.market_snapshot.filter(
          (row) =>
            row.metric === metric &&
            (row.geography === geography ||
              row.geography.startsWith(geography + ' ('))
        )
      )
    }))
  }))
  return {
    metrics,
    regions,
    coveredCells: regions.reduce(
      (n, r) => n + r.cells.filter((c) => c.observations.length > 0).length,
      0
    ),
    totalCells: regions.length * metrics.length,
    readyCharts: report.charts.filter((c) => c.status === 'ready'),
    unavailableCharts: report.charts.filter((c) => c.status !== 'ready'),
    gapGroups: report.geographies
      .map((geography) => ({
        geography,
        current: report.data_gaps.filter(
          (g) => g.geography === geography && g.component !== 'history'
        ),
        history: report.data_gaps.filter(
          (g) => g.geography === geography && g.component === 'history'
        )
      }))
      .filter((g) => g.current.length || g.history.length)
  }
}
