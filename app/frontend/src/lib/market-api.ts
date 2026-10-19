import type { PublisherReportedChange } from './chat-evidence'

export const MARKET_API = (
  process.env.NEXT_PUBLIC_MARKET_API_URL || 'http://127.0.0.1:8000/api/market'
).replace(/\/$/, '')
export type Fact = {
  id: string
  metric: string
  value: string | null
  normalized_value?: string | null
  unit?: string
  geography: string
  period: string
  status: string
  human_review_status?: string
  publisher?: string
  source_id: string
  document_id: string
  evidence?: { quote?: string; page?: number | null; locator?: string }
  definition?: string
  grade?: string
  method?: string
  run_id?: string
  published_at?: string
  collected_at?: string
  issues?: string[]
  eligible_for_comparison?: boolean
}
export type Source = {
  id: string
  name: string
  category?: string
  url: string
  enabled: boolean
  health: string
  last_success?: string
  last_error?: string
}
export type Job = {
  id: string
  kind: string
  status: string
  stage?: string
  progress?: number
  started_at?: string
  finished_at?: string
  error?: string
  attempts?: number
  run_id?: string
  source_id?: string
  document_id?: string
  result?: { report_id?: string; [key: string]: unknown }
  plan?: {
    scope: {
      geographies: string[]
      metrics: string[]
      observation_period?: string | null
      requested_periods?: string[]
    }
    decision: string
    nodes: {
      id: string
      status: string
      required: boolean
      depends_on: string[]
    }[]
    next_checks: unknown[]
    adaptation?: {
      missing_cells: number
      deferred_cells: number
      passes: number
      limit: number
      decision: string
    }
  }
  checkpoints?: Record<
    string,
    { status: string; reused?: boolean; elapsed_ms?: number }
  >
}
export type MarketEvent = Partial<PublisherReportedChange> & {
  id: string
  title: string
  summary: string
  kind: string
  importance: string
  status: string
  geography?: string
  published_at?: string
  source_id?: string
  url?: string
  document_id?: string
}
export type Document = {
  id: string
  title?: string
  url?: string
  source_id?: string
  published_at?: string
  collected_at?: string
  sha256?: string
  media?: string
}
export type Report = {
  id: string
  title: string
  created_at: string
  period: string
  status?: string
  report_type?: string
  generation_status?: string
  markdown_url?: string
  html_url?: string
}
export type Comparison = {
  id?: string
  old_id?: string
  new_id?: string
  status?: string
  reason?: string
  reasons?: string[]
  delta?: string | number | null
  absolute_change?: string | number | null
  change_unit?: string
  metric?: string
  geography?: string
  old?: Fact
  new?: Fact
}
export type Settings = {
  news_interval_hours: number
  market_interval_hours: number
  notifications_enabled: boolean
  rent_threshold_pct?: number
  takeup_threshold_pct?: number
  vacancy_threshold_pp?: number
  notification_configured: boolean
  monitoring_enabled?: boolean
  monitor_analysis_enabled?: boolean
  geographies: string[]
  metrics: string[]
  schedules?: {
    name?: string
    kind?: string
    cron_expr?: string
    next_run_at?: string | number
    enabled?: boolean
  }[]
}
export type DirectionalSeries = {
  metric: string
  metric_label?: string
  geography: string
  definition?: string
  unit?: string
  direction: 'up' | 'down' | 'flat'
  signal?: string
  absolute_change: string
  relative_change_pct?: string | null
  change_unit?: string
  from_period: string
  to_period: string
  fact_ids?: string[]
  periods?: string[]
  points?: number
  confidence?: string
  reviewed?: boolean
  basis?: string
  assumption?: string
}
export type Directional = {
  version?: string
  status: 'available' | 'insufficient'
  series: DirectionalSeries[]
  reviewed_series?: number
  candidate_series?: number
  stance?: string
  summary?: string
}
export type ReviewRecord = {
  id: string
  fact_id?: string
  decision: ReviewDecision
  reviewer: string
  note?: string
  at?: string
  created_at?: string
  prior_status?: string
  prior_review_status?: string
  annualization?: string
  blockers?: string[]
}
export type Overview = {
  updated_at: string | null
  facts: Fact[]
  events: MarketEvent[]
  sources: Source[]
  counts: {
    facts: number
    events: number
    documents: number
    reports: number
    needs_review: number
    validated?: number
    pending_human_review?: number
  }
  comparisons: Comparison[]
  jobs: Job[]
  directional?: Directional
}
export type Evidence = {
  fact: Fact
  document: Document
  evidence: { quote?: string; page?: number | null; locator?: string }
  download_url?: string
  approval?: { eligible: boolean; blockers: string[] }
  reviews?: ReviewRecord[]
}

export type ReviewDecision = 'approve' | 'reject' | 'reopen'

export function reviewFact(
  id: string,
  decision: ReviewDecision,
  reviewer: string,
  note = ''
) {
  return write<{ fact: Fact; review: Record<string, unknown> }>(
    `/facts/${encodeURIComponent(id)}/review`,
    { decision, reviewer, note }
  )
}
export type List<T> = { items: T[]; total?: number; updated_at?: string }

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30000)
  try {
    const response = await fetch(`${MARKET_API}${path}`, {
      ...options,
      signal: options?.signal || controller.signal,
      headers: {
        ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
        ...options?.headers
      }
    })
    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: response.statusText }))
      throw new Error(
        typeof error.detail === 'string'
          ? error.detail
          : `Request failed (${response.status})`
      )
    }
    return response.json()
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError')
      throw new Error(
        'The request timed out. Check Job Status before retrying a write.'
      )
    throw error
  } finally {
    clearTimeout(timeout)
  }
}
export function write<T>(path: string, body?: unknown, method = 'POST') {
  return api<T>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
    headers: { 'Idempotency-Key': crypto.randomUUID() }
  })
}
export function fileUrl(path?: string) {
  if (!path) return undefined
  if (path.startsWith('/api/market'))
    return `${new URL(MARKET_API).origin}${path}`
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  return `${MARKET_API}/${path.replace(/^\//, '')}`
}
export function externalUrl(path?: string) {
  if (!path) return undefined
  try {
    const url = new URL(path)
    return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined
  } catch {
    return undefined
  }
}
