'use client'

import Link from 'next/link'
import { usePathname, useSearchParams } from 'next/navigation'
import {
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState
} from 'react'
import {
  Activity,
  ArrowDownToLine,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Clock3,
  Database,
  FileText,
  LayoutDashboard,
  MessageSquare,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  X
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import {
  Comparison,
  Directional,
  Document,
  Evidence,
  externalUrl,
  Fact,
  fileUrl,
  Job,
  List,
  MARKET_API,
  MarketEvent,
  Overview,
  Report,
  reviewFact,
  ReviewDecision,
  Settings,
  Source,
  write
} from '@/lib/market-api'
import { useMarket } from '@/hooks/useMarket'
import { readMarketStream } from '@/lib/market-stream'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  jobPresentation,
  retryableJob,
  researchLink,
  reviewMeaning
} from '@/lib/workflow'
import CoveragePicker from './CoveragePicker'
import IndicatorCoverage from './IndicatorCoverage'
import SavedReport, { ReportView } from './ReportArtifact'
import type { ReportArtifact } from '@/lib/report-artifact'

const pages = [
  {
    path: '/overview',
    title: 'Market Overview',
    icon: LayoutDashboard,
    subtitle: 'The latest evidence from the London office market.'
  },
  {
    path: '/market-data',
    title: 'Market Data',
    icon: Database,
    subtitle: 'Filter reported metrics and trace every number to its source.'
  },
  {
    path: '/events',
    title: 'Changes & Events',
    icon: Activity,
    subtitle: 'Track market developments and compare eligible observations.'
  },
  {
    path: '/ask',
    title: 'Saved-record research',
    icon: MessageSquare,
    subtitle:
      'Ask a question, inspect the evidence, and keep the answer grounded.'
  },
  {
    path: '/reports',
    title: 'Reports',
    icon: FileText,
    subtitle: 'Generate a dated briefing from the saved market record.'
  },
  {
    path: '/settings',
    title: 'Monitor Settings',
    icon: Settings2,
    subtitle: 'Control collection, coverage, and notification preferences.'
  },
  {
    path: '/jobs',
    title: 'Job Status',
    icon: ClipboardList,
    subtitle:
      'Follow collection and extraction work without keeping a request open.'
  }
]
const inputClass =
  'h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-100'
const actionClass =
  'bg-teal-800 text-white hover:bg-teal-900 focus-visible:ring-teal-500'
function human(value?: string | number | null) {
  return value === undefined || value === null || value === ''
    ? 'Not available'
    : String(value).replace(/_/g, ' ')
}
function time(value?: string | number | null) {
  if (!value) return 'Not available'
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const dateOnly = new Date(`${value}T00:00:00Z`)
    return Number.isNaN(dateOnly.getTime())
      ? value
      : dateOnly.toLocaleDateString('en-GB', {
          dateStyle: 'medium',
          timeZone: 'UTC'
        })
  }
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
}
function Badge({ value }: { value?: string }) {
  return (
    <span
      className={cn(
        'inline-flex rounded-full border px-2 py-0.5 text-xs font-medium',
        [
          'validated',
          'completed',
          'succeeded',
          'healthy',
          'ok',
          'sent',
          'acknowledged'
        ].includes(value || '')
          ? 'border-teal-200 bg-teal-50 text-teal-800'
          : ['failed', 'error', 'unhealthy'].includes(value || '')
            ? 'border-red-200 bg-red-50 text-red-800'
            : 'border-slate-200 bg-slate-50 text-slate-600'
      )}
    >
      {human(value)}
    </span>
  )
}
function Panel({
  title,
  subtitle,
  action,
  children
}: {
  title: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div>
          <h2 className="text-balance text-base font-semibold text-slate-900">
            {title}
          </h2>
          {subtitle && (
            <p className="mt-1 text-pretty text-xs text-slate-500">
              {subtitle}
            </p>
          )}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}
function Empty({
  children,
  href,
  label
}: {
  children: ReactNode
  href?: string
  label?: string
}) {
  return (
    <div className="px-6 py-10 text-center">
      <CircleHelp className="mx-auto mb-3 size-6 text-slate-400" />
      <p className="text-pretty text-sm text-slate-500">{children}</p>
      {href && (
        <Link
          href={href}
          className="mt-3 inline-flex text-sm font-medium text-teal-800 underline underline-offset-4"
        >
          {label}
        </Link>
      )}
    </div>
  )
}
function Status({
  loading,
  error,
  reload
}: {
  loading: boolean
  error: string
  reload: () => unknown
}) {
  return (
    <>
      {loading && (
        <div className="space-y-3 p-5" aria-label="Loading market records">
          <Skeleton className="h-5 w-2/3 bg-slate-100" />
          <Skeleton className="h-16 w-full bg-slate-100" />
          <Skeleton className="h-16 w-full bg-slate-100" />
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="m-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          <p>{error}</p>
          <Button
            className="mt-2 border-red-200 bg-white text-red-800 hover:bg-red-100"
            onClick={() => void reload()}
          >
            Retry loading
          </Button>
        </div>
      )}
    </>
  )
}
function Stamp({ updated }: { updated?: number }) {
  return (
    <p className="text-xs tabular-nums text-slate-500">
      Last checked {time(updated)} · cached records load first
    </p>
  )
}
type Action = <T>(
  key: string,
  task: () => Promise<T>,
  success?: (data: T) => void
) => Promise<void>

export default function MarketApp() {
  const path = usePathname()
  const params = useSearchParams()
  const page = pages.find((p) => p.path === path) || pages[0]
  const sourceState = useMarket<List<Source>>('/sources')
  const [runtime, setRuntime] = useState<{
    mode: 'live' | 'mock'
    data_asof: string | null
  } | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    const origin = new URL(MARKET_API).origin
    void fetch(`${origin}/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Health check failed')
        return response.json()
      })
      .then((value) => setRuntime(value))
      .catch(() => setRuntime(null))
    return () => controller.abort()
  }, [])
  const [evidenceId, setEvidenceId] = useState<string | null>(
    params.get('evidence')
  )
  useEffect(() => setEvidenceId(params.get('evidence')), [params])
  const [busy, setBusy] = useState<string | null>(null)
  const pending = useRef(false)
  const [message, setMessage] = useState('')
  const [actionError, setActionError] = useState('')
  const act: Action = async (key, task, success) => {
    if (pending.current) return
    pending.current = true
    setBusy(key)
    setMessage('')
    setActionError('')
    try {
      const result = await task()
      success?.(result)
    } catch (e) {
      setActionError(
        e instanceof Error
          ? e.message
          : 'The action failed. Check Job Status before retrying.'
      )
    } finally {
      pending.current = false
      setBusy(null)
    }
  }
  const refresh = (id?: string) =>
    void act(
      id || 'refresh',
      () =>
        write<Job>(
          id ? `/sources/${encodeURIComponent(id)}/refresh` : '/refresh'
        ),
      (job) => {
        setMessage(
          `Collection accepted. Job ${job.id} is ${human(job.status)}. Follow progress in Job Status.`
        )
        void sourceState.reload()
      }
    )
  return (
    <div className="market-root min-h-full bg-slate-50 font-sans text-slate-900">
      <div className="min-w-0 flex-1">
        <header className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-5 py-3 lg:px-8">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span>London office market</span>
            <ChevronRight className="size-3" />
            <span className="font-medium text-slate-800">{page.title}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700">
              Mode: {runtime?.mode ?? 'unavailable'} · data as of:{' '}
              {runtime?.data_asof
                ? time(runtime.data_asof)
                : 'data insufficient'}
            </span>
            <span className="text-xs text-slate-500">
              {sourceState.data
                ? `${sourceState.data.items.filter((s) => ['healthy', 'ok'].includes(s.health)).length}/${sourceState.data.items.length} sources healthy`
                : sourceState.error
                  ? 'Source service unavailable'
                  : 'Checking sources…'}
              <span className="sr-only">
                Source availability is not evidence verification.
              </span>
            </span>
            <Button
              disabled={Boolean(busy) || runtime?.mode === 'mock'}
              onClick={() => refresh()}
              className={actionClass}
              title={
                runtime?.mode === 'mock'
                  ? 'External refresh is disabled in credential-free mock mode.'
                  : undefined
              }
            >
              <RefreshCw className="size-4" />
              {busy === 'refresh'
                ? 'Starting…'
                : runtime?.mode === 'mock'
                  ? 'Refresh disabled in mock'
                  : 'Refresh sources'}
            </Button>
          </div>
        </header>
        <main className="mx-auto max-w-7xl space-y-6 p-5 lg:p-8">
          <div>
            <p className="mb-2 text-xs font-medium text-teal-800">
              LONDON · OFFICE SECTOR
            </p>
            <h1 className="text-balance text-2xl font-semibold text-slate-950">
              {page.title}
            </h1>
            <p className="mt-2 text-pretty text-sm text-slate-500">
              {page.subtitle}
            </p>
          </div>
          {message && (
            <div
              role="status"
              className="flex items-start justify-between gap-4 rounded-lg border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900"
            >
              <span>
                {message}{' '}
                <Link href="/jobs" className="underline">
                  View jobs
                </Link>
              </span>
              <button
                aria-label="Dismiss message"
                onClick={() => setMessage('')}
              >
                <X className="size-4" />
              </button>
            </div>
          )}
          {actionError && (
            <div
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"
            >
              {actionError}
            </div>
          )}
          {path === '/overview' && <OverviewPage evidence={setEvidenceId} />}
          {path === '/market-data' && (
            <DataPage
              evidence={setEvidenceId}
              act={act}
              busy={busy}
              notify={setMessage}
            />
          )}
          {path === '/events' && (
            <EventsPage act={act} busy={busy} notify={setMessage} />
          )}
          {path === '/ask' && (
            <AskPage evidence={setEvidenceId} runtimeMode={runtime?.mode} />
          )}
          {path === '/reports' && (
            <ReportsPage
              act={act}
              busy={busy}
              notify={setMessage}
              runtimeMode={runtime?.mode}
            />
          )}
          {path === '/settings' && (
            <SettingsPage act={act} busy={busy} notify={setMessage} />
          )}
          {path === '/jobs' && (
            <JobsPage act={act} busy={busy} notify={setMessage} />
          )}
          <details className="rounded-xl border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer text-sm font-medium">
              Source collection details · availability is separate from
              verification
            </summary>
            <div className="mt-4">
              <SourceHealth state={sourceState} refresh={refresh} busy={busy} />
            </div>
          </details>
          <footer className="flex flex-wrap justify-between gap-3 border-t border-slate-200 pt-4 text-xs text-slate-500">
            <span>DeepInsight Lite · Saved London office market evidence</span>
            <details>
              <summary>Service details</summary>API {MARKET_API}
            </details>
          </footer>
        </main>
      </div>
      <EvidenceDrawer id={evidenceId} close={() => setEvidenceId(null)} />
    </div>
  )
}

function FactTable({
  facts,
  evidence
}: {
  facts: Fact[]
  evidence: (id: string) => void
}) {
  const params = useSearchParams()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [reviewer, setReviewer] = useState('')
  const [bulkBusy, setBulkBusy] = useState(false)
  const [bulkError, setBulkError] = useState('')
  const [bulkMessage, setBulkMessage] = useState('')
  useEffect(() => {
    setReviewer(window.localStorage.getItem('market-reviewer') || '')
  }, [])
  const pending = facts.filter(
    (f) =>
      f.human_review_status === 'pending_review' ||
      f.status === 'pending_review'
  )
  const pendingIds = new Set(pending.map((f) => f.id))
  const allSelected =
    pending.length > 0 && pending.every((f) => selected.has(f.id))
  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const toggleAll = () => {
    if (allSelected) setSelected(new Set())
    else setSelected(new Set(pendingIds))
  }
  const bulkApprove = async () => {
    const name = reviewer.trim()
    if (name.length < 2) {
      setBulkError('Enter your name (at least 2 characters) for bulk approval.')
      return
    }
    if (selected.size === 0) return
    setBulkBusy(true)
    setBulkError('')
    setBulkMessage('')
    let ok = 0
    let fail = 0
    for (const id of selected) {
      try {
        await reviewFact(
          id,
          'approve',
          name,
          'Bulk approved from observation list.'
        )
        ok++
      } catch {
        fail++
      }
    }
    window.localStorage.setItem('market-reviewer', name)
    setBulkMessage(
      `Approved ${ok} observation(s)${fail ? `, ${fail} failed` : ''}.`
    )
    setSelected(new Set())
    setBulkBusy(false)
    window.dispatchEvent(new Event('market:refresh'))
  }
  return (
    <div className="overflow-x-auto">
      {pending.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-3 rounded-lg bg-amber-50 px-4 py-3 text-sm">
          <label className="flex items-center gap-2 text-slate-700">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="size-4 accent-teal-800"
            />
            Select all {pending.length} pending
          </label>
          <input
            className="w-40 rounded-md border border-slate-300 px-2 py-1 text-sm"
            placeholder="Reviewer name"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            maxLength={80}
          />
          <Button
            size="sm"
            disabled={bulkBusy || selected.size === 0}
            onClick={() => void bulkApprove()}
          >
            {bulkBusy ? 'Approving…' : `Approve selected (${selected.size})`}
          </Button>
          {bulkError && (
            <span className="text-xs text-red-700">{bulkError}</span>
          )}
          {bulkMessage && (
            <span className="text-xs text-teal-800">{bulkMessage}</span>
          )}
        </div>
      )}
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs text-slate-500">
          <tr>
            <th className="px-3 py-3"></th>
            {[
              'Metric / geography',
              'Reported value',
              'Period',
              'Review status',
              'Publisher',
              'Evidence & next steps'
            ].map((h) => (
              <th
                key={h}
                scope="col"
                className="whitespace-nowrap px-5 py-3 font-medium"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {facts.map((f) => {
            const isPending =
              f.human_review_status === 'pending_review' ||
              f.status === 'pending_review'
            return (
              <tr key={f.id} className="hover:bg-slate-50">
                <td className="px-3 py-4">
                  {isPending && (
                    <input
                      type="checkbox"
                      checked={selected.has(f.id)}
                      onChange={() => toggle(f.id)}
                      className="size-4 accent-teal-800"
                    />
                  )}
                </td>
                <td className="px-5 py-4">
                  <span className="font-medium">{human(f.metric)}</span>
                  <span className="mt-1 block text-xs text-slate-500">
                    {human(f.geography)}
                  </span>
                </td>
                <td className="min-w-48 px-5 py-4 font-semibold tabular-nums">
                  {f.value ?? 'Unknown'}{' '}
                  <span className="font-normal text-slate-500">
                    {human(f.unit)}
                  </span>
                </td>
                <td className="whitespace-nowrap px-5 py-4 tabular-nums">
                  {human(f.period)}
                </td>
                <td className="px-5 py-4">
                  <Badge value={f.status} />
                </td>
                <td className="px-5 py-4 text-xs text-slate-500">
                  {f.publisher || f.source_id}
                </td>
                <td className="px-5 py-4">
                  <button
                    className="whitespace-nowrap font-medium text-teal-800 underline underline-offset-4"
                    onClick={() => evidence(f.id)}
                  >
                    View evidence
                  </button>
                  <Link
                    className="mt-2 block whitespace-nowrap text-xs text-teal-800 underline"
                    href={researchLink('fact', f.id, params.toString())}
                  >
                    Analyze with AI
                  </Link>
                  <Link
                    className="mt-2 block whitespace-nowrap text-xs text-teal-800 underline"
                    href={`/market-data?compare=${encodeURIComponent(f.id)}#comparison`}
                  >
                    Compare observations
                  </Link>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function DirectionalPanel({ directional }: { directional?: Directional }) {
  const series = directional?.series || []
  const reviewed = series.filter((s) => s.reviewed).length
  return (
    <Panel
      title="Comparable two-period directions"
      subtitle={
        series.length
          ? `${reviewed} of ${series.length} series are human-reviewed. Change is arithmetic between two saved observations that share metric, area, definition and unit. A direction is evidence, not a forecast.`
          : 'No two observations of the same metric, area, definition and unit have been saved yet.'
      }
    >
      {series.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-4 font-medium">Metric &amp; area</th>
                <th className="py-2 pr-4 font-medium">Periods</th>
                <th className="py-2 pr-4 font-medium">Change</th>
                <th className="py-2 pr-4 font-medium">Direction</th>
                <th className="py-2 pr-4 font-medium">Review</th>
              </tr>
            </thead>
            <tbody>
              {series.map((s) => (
                <tr
                  key={`${s.metric}-${s.geography}-${s.to_period}`}
                  className="border-b border-slate-100 align-top"
                >
                  <td className="py-3 pr-4">
                    <p className="font-medium">
                      {s.metric_label || human(s.metric)}
                    </p>
                    <p className="text-xs text-slate-500">{s.geography}</p>
                  </td>
                  <td className="py-3 pr-4 tabular-nums text-slate-600">
                    {s.from_period} → {s.to_period}
                  </td>
                  <td className="py-3 pr-4 tabular-nums">
                    {s.absolute_change} {s.change_unit || s.unit}
                    {s.relative_change_pct ? (
                      <span className="block text-xs text-slate-500">
                        {s.relative_change_pct}%
                      </span>
                    ) : null}
                  </td>
                  <td className="py-3 pr-4">
                    {human(s.direction)}
                    {s.signal ? (
                      <span className="block text-xs text-slate-500">
                        {s.signal}
                      </span>
                    ) : null}
                  </td>
                  <td className="py-3 pr-4">
                    <Badge
                      value={s.reviewed ? 'validated' : 'pending_review'}
                    />
                    {s.assumption === 'industry_convention' ? (
                      <p className="mt-1 text-xs text-amber-700">
                        Annual rent assumed by convention; confirm the time
                        denominator before relying on it.
                      </p>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="p-4 text-sm text-slate-600">
          Unreviewed or differently defined records are never compared. Approve
          a second period in the same series to see a direction here.
        </p>
      )}
    </Panel>
  )
}

function OverviewPage({ evidence }: { evidence: (id: string) => void }) {
  const state = useMarket<Overview>('/overview')
  const data = state.data
  useEffect(() => {
    if (
      data &&
      performance.getEntriesByName('market-overview-primary-ready').length === 0
    ) {
      performance.mark('market-overview-primary-ready', {
        detail: { fact_count: data.counts.facts }
      })
    }
  }, [data])
  return (
    <>
      <Status {...state} />
      {data && (
        <>
          <section
            className="rounded-xl border border-slate-200 bg-white p-5 text-sm"
            aria-label="Research starting point"
          >
            <h2 className="font-semibold">
              Start with the evidence, then investigate
            </h2>
            <p className="mt-2 text-slate-600">
              Visible saved reporting periods:{' '}
              {Array.from(
                new Set(data.facts.map((f) => f.period).filter(Boolean))
              ).join(', ') || 'Not supplied'}
              . These are source reporting periods, not a live market reading.
            </p>
            <p className="mt-2 text-slate-600">
              {data.counts.needs_review} observations await review. Source
              availability and recent collection do not verify the reported
              values. Inspect a source, continue with AI, or prepare a briefing
              below.
            </p>
            <div className="mt-3 flex flex-wrap gap-4">
              <Link className="text-teal-800 underline" href="/events">
                Investigate developments
              </Link>
              <Link className="text-teal-800 underline" href="/reports">
                Prepare a briefing
              </Link>
              <Link className="text-teal-800 underline" href="/settings">
                Review monitoring
              </Link>
            </div>
          </section>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {[
              {
                label: 'Saved observations',
                value: data.counts.facts,
                detail: 'Traceable to original documents',
                icon: Database
              },
              {
                label: 'Human-reviewed',
                value: data.counts.validated ?? 0,
                detail: 'Approved by a named reviewer',
                icon: Check
              },
              {
                label: 'Awaiting review',
                value:
                  data.counts.pending_human_review ?? data.counts.needs_review,
                detail: 'Excluded from formal comparisons',
                icon: ShieldCheck
              },
              {
                label: 'Source documents',
                value: data.counts.documents,
                detail: 'Original files retained',
                icon: FileText
              },
              {
                label: 'Market events',
                value: data.counts.events,
                detail: 'Updates in the saved record',
                icon: Activity
              }
            ].map((card) => (
              <div
                key={card.label}
                className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <div className="flex items-center justify-between text-sm text-slate-500">
                  {card.label}
                  <card.icon className="size-4" />
                </div>
                <p className="mt-3 text-xl font-semibold tabular-nums">
                  {card.value}
                </p>
                <p className="mt-2 text-xs text-slate-500">{card.detail}</p>
              </div>
            ))}
          </div>
          <DirectionalPanel directional={data.directional} />
          <Panel
            title="Latest market observations"
            subtitle={`Saved record updated ${time(data.updated_at)}`}
            action={
              <Link
                className="text-xs font-medium text-teal-800"
                href="/market-data"
              >
                Explore all data →
              </Link>
            }
          >
            {data.facts.length ? (
              <FactTable facts={data.facts.slice(0, 6)} evidence={evidence} />
            ) : (
              <Empty href="/settings" label="Review collection sources">
                No market observations collected yet.
              </Empty>
            )}
          </Panel>
          <div className="grid gap-6 lg:grid-cols-2">
            <Panel
              title="Recent developments"
              action={
                <Link className="text-xs text-teal-800" href="/events">
                  All events →
                </Link>
              }
            >
              {data.events.length ? (
                <EventList events={data.events.slice(0, 3)} />
              ) : (
                <Empty href="/settings" label="Check enabled sources">
                  No recent events in the saved record.
                </Empty>
              )}
            </Panel>
            <Panel
              title="Background work"
              action={
                <Link className="text-xs text-teal-800" href="/jobs">
                  All jobs →
                </Link>
              }
            >
              {data.jobs.length ? (
                <div className="divide-y divide-slate-100">
                  {data.jobs.slice(0, 4).map((j) => (
                    <div
                      key={j.id}
                      className="flex items-center justify-between gap-3 p-4"
                    >
                      <div>
                        <p className="text-sm font-medium">{human(j.kind)}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {human(j.stage)} · {time(j.started_at)}
                        </p>
                      </div>
                      <Badge value={j.status} />
                    </div>
                  ))}
                </div>
              ) : (
                <Empty href="/jobs" label="View job history">
                  No jobs have run yet. Use Refresh sources to collect a new
                  snapshot.
                </Empty>
              )}
            </Panel>
          </div>
        </>
      )}
      <Stamp updated={state.updated} />
    </>
  )
}

function Filter({
  label,
  value,
  onChange,
  options
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
}) {
  return (
    <label className="min-w-36 flex-1 text-xs font-medium text-slate-600">
      {label}
      <select
        className={cn(inputClass, 'mt-2')}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">All {label.toLowerCase()}</option>
        {Array.from(new Set(options.filter(Boolean))).map((value) => (
          <option key={value} value={value}>
            {human(value)}
          </option>
        ))}
      </select>
    </label>
  )
}

function DataPage({
  evidence,
  act,
  busy,
  notify
}: {
  evidence: (id: string) => void
  act: Action
  busy: string | null
  notify: (value: string) => void
}) {
  const filters = useSearchParams()
  const [geo, setGeo] = useState(filters.get('geography') || ''),
    [metric, setMetric] = useState(filters.get('metric') || ''),
    [period, setPeriod] = useState(filters.get('period') || ''),
    [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)
  const all = useMarket<List<Fact>>('/facts?limit=500')
  const settings = useMarket<Settings>('/settings')
  const documents = useMarket<List<Document>>('/documents')
  const query = new URLSearchParams({ limit: '50', offset: String(offset) })
  for (const [key, value] of Object.entries({
    geography: geo,
    metric,
    period,
    status
  }))
    if (value) query.set(key, value)
  const state = useMarket<List<Fact>>(`/facts?${query}`)
  const options = all.data?.items || []
  const update = (setter: (value: string) => void) => (value: string) => {
    setter(value)
    setOffset(0)
  }
  return (
    <>
      <Status loading={false} error={all.error} reload={all.reload} />
      <div className="flex flex-wrap gap-4 rounded-xl border border-slate-200 bg-white p-5">
        <Filter
          label="Geographies"
          value={geo}
          onChange={update(setGeo)}
          options={[
            ...(settings.data?.geographies || []),
            ...options.map((f) => f.geography)
          ]}
        />
        <Filter
          label="Metrics"
          value={metric}
          onChange={update(setMetric)}
          options={[
            ...(settings.data?.metrics || []),
            ...options.map((f) => f.metric)
          ]}
        />
        <Filter
          label="Periods"
          value={period}
          onChange={update(setPeriod)}
          options={options.map((f) => f.period)}
        />
        <Filter
          label="Statuses"
          value={status}
          onChange={update(setStatus)}
          options={[
            'pending_review',
            'needs_review',
            'validated',
            ...options.map((f) => f.status)
          ]}
        />
      </div>
      <Panel
        title="Market data"
        subtitle={`${state.data?.total ?? 0} matching observations · values retain publisher units`}
      >
        <Status {...state} />
        {state.data?.items.length ? (
          <FactTable facts={state.data.items} evidence={evidence} />
        ) : (
          !state.loading &&
          !state.error && (
            <Empty href="/settings" label="Review collection sources">
              No observations match these filters. Change a filter or collect a
              source.
            </Empty>
          )
        )}
        <div className="flex items-center justify-between border-t border-slate-100 p-4">
          <p className="text-xs text-slate-500">
            Showing {state.data?.items.length ? offset + 1 : 0}–
            {offset + (state.data?.items.length || 0)} of{' '}
            {state.data?.total || 0}
          </p>
          <div className="flex gap-2">
            <Button
              className="border border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              Previous
            </Button>
            <Button
              className="border border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
              disabled={offset + 50 >= (state.data?.total || 0)}
              onClick={() => setOffset(offset + 50)}
            >
              Next
            </Button>
          </div>
        </div>
      </Panel>
      <details
        open={Boolean(filters.get('compare'))}
        className="rounded-xl border border-slate-200 bg-white p-4"
      >
        <summary className="cursor-pointer text-sm font-semibold">
          Compare saved observations
        </summary>
        <p className="my-3 text-sm text-slate-600">
          The service checks review status, definitions, geography and units.
          Unreviewed inputs remain blocked; opening this panel does not approve
          data.
        </p>
        <ComparisonsPanel
          act={act}
          busy={busy}
          notify={notify}
          initialId={filters.get('compare') || ''}
        />
      </details>
      <Panel
        title="Source document archive"
        subtitle="LLM extraction runs only when you explicitly select a document. It may use the configured model provider."
      >
        <Status {...documents} />
        {documents.data?.items.length ? (
          <div className="divide-y divide-slate-100">
            {documents.data.items.map((d) => (
              <div
                key={d.id}
                className="flex flex-wrap items-center justify-between gap-3 p-4"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">{d.title || d.id}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {d.media} · Collected {time(d.collected_at)}
                  </p>
                </div>
                <div className="flex gap-3">
                  <a
                    className="self-center text-xs text-teal-800 underline"
                    target="_blank"
                    rel="noreferrer"
                    href={`${MARKET_API}/documents/${encodeURIComponent(d.id)}/file`}
                  >
                    Original file
                  </a>
                  <Button
                    className={actionClass}
                    disabled={!!busy}
                    onClick={() =>
                      void act(
                        `extract-${d.id}`,
                        () =>
                          write<Job>(
                            `/documents/${encodeURIComponent(d.id)}/extract`
                          ),
                        (j) =>
                          notify(
                            `Extraction job ${j.id} accepted (${human(j.status)}).`
                          )
                      )
                    }
                  >
                    Extract this document
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          !documents.loading && (
            <Empty href="/settings" label="Collect a source">
              No documents available for extraction.
            </Empty>
          )
        )}
      </Panel>
      <Stamp updated={state.updated} />
    </>
  )
}

function EventList({
  events,
  ack,
  busy
}: {
  events: MarketEvent[]
  ack?: (id: string) => void
  busy?: string | null
}) {
  const researchParams = useSearchParams()
  const selectedId = researchParams.get('event')
  useEffect(() => {
    if (selectedId && events.some((event) => event.id === selectedId))
      document
        .getElementById(`event-${selectedId}`)
        ?.scrollIntoView({ block: 'center' })
  }, [selectedId, events])
  return (
    <div className="divide-y divide-slate-100">
      {events.map((e) => (
        <article
          key={e.id}
          id={`event-${e.id}`}
          className={`space-y-3 p-5 ${selectedId === e.id ? 'ring-2 ring-inset ring-teal-600' : ''}`}
        >
          <div className="flex flex-wrap gap-2">
            <Badge value={e.kind} />
            <Badge value={e.importance} />
            <Badge value={e.status} />
          </div>
          <h3 className="text-balance text-sm font-semibold">{e.title}</h3>
          <p className="text-xs text-slate-500">
            Source excerpt ·{' '}
            {reviewMeaning(
              e.human_review_status ||
                (e.status === 'acknowledged' ? undefined : e.status)
            )}
          </p>
          <blockquote className="text-pretty text-sm leading-6 text-slate-600">
            {e.summary.length > 320 ? `${e.summary.slice(0, 320)}…` : e.summary}
          </blockquote>
          {e.summary.length > 320 && (
            <details className="text-sm">
              <summary>Full saved source excerpt</summary>
              <p className="mt-2 whitespace-pre-wrap">{e.summary}</p>
            </details>
          )}
          <Link
            className="inline-block text-sm text-teal-800 underline"
            href={researchLink('event', e.id, researchParams.toString())}
          >
            Explain this event with AI
          </Link>
          {e.kind === 'publisher_reported_change' && (
            <details className="text-sm">
              <summary>
                Publisher-reported change · source evidence ·{' '}
                {e.human_review_status || e.status}
              </summary>
              <p className="my-2">
                Institution disclosure; not a system-calculated change or
                independently verified fact. Human review:
                {e.human_review_status || e.status}
              </p>
              <p>
                {e.definition} · {e.geography} · {e.period} · Comparison period:{' '}
                {e.comparison_period || 'Not disclosed'}
              </p>
              <p>
                Reported value: {e.reported_value ?? 'Not disclosed'}{' '}
                {e.reported_unit} · Reported change:{' '}
                {e.reported_change ?? 'Not disclosed'} {e.change_unit}
              </p>
              <p>
                System calculation:{' '}
                {e.calculation_performed === false
                  ? 'Not performed'
                  : 'Not confirmed'}
              </p>
              <p>
                {e.report_title || e.document_id} · Published:{' '}
                {e.published_at || 'Not disclosed'}
              </p>
              <blockquote className="my-2 border-l-2 pl-3">
                {e.evidence?.quote || 'No quotation supplied'}
              </blockquote>
              <p>
                Page: {e.evidence?.page ?? 'N/A'} ·{' '}
                {e.evidence?.locator || 'No locator'}
              </p>
              <p className="break-all">
                Record: {e.id}
                <br />
                Document: {e.document_id}
                <br />
                SHA-256: {e.document_sha256 || 'Not supplied'}
              </p>
              <p>{e.limitation}</p>
            </details>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
            <span>
              {human(e.geography)} · {time(e.published_at)}
            </span>
            <div className="flex items-center gap-3">
              {externalUrl(e.url) && (
                <a
                  target="_blank"
                  rel="noreferrer"
                  href={externalUrl(e.url)}
                  className="text-teal-800 underline"
                >
                  Original source
                </a>
              )}
              {ack && (
                <Button
                  className="border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  disabled={!!busy || e.status === 'acknowledged'}
                  onClick={() => ack(e.id)}
                >
                  <Check className="size-3" />
                  {e.status === 'acknowledged' ? 'Acknowledged' : 'Acknowledge'}
                </Button>
              )}
            </div>
          </div>
        </article>
      ))}
    </div>
  )
}
function EventsPage({
  act,
  busy,
  notify
}: {
  act: Action
  busy: string | null
  notify: (value: string) => void
}) {
  const [geo, setGeo] = useState(''),
    [kind, setKind] = useState(''),
    [importance, setImportance] = useState(''),
    [status, setStatus] = useState('')
  const all = useMarket<List<MarketEvent>>('/events')
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries({
    geography: geo,
    kind,
    importance,
    status
  }))
    if (v) params.set(k, v)
  const state = useMarket<List<MarketEvent>>(`/events?${params}`)
  return (
    <>
      <div className="flex flex-wrap gap-4 rounded-xl border border-slate-200 bg-white p-5">
        <Filter
          label="Geographies"
          value={geo}
          onChange={setGeo}
          options={(all.data?.items || []).map((e) => e.geography || '')}
        />
        <Filter
          label="Kinds"
          value={kind}
          onChange={setKind}
          options={(all.data?.items || []).map((e) => e.kind)}
        />
        <Filter
          label="Importance"
          value={importance}
          onChange={setImportance}
          options={[
            'high',
            'medium',
            'low',
            ...(all.data?.items || []).map((e) => e.importance)
          ]}
        />
        <Filter
          label="Statuses"
          value={status}
          onChange={setStatus}
          options={[
            'new',
            'acknowledged',
            ...(all.data?.items || []).map((e) => e.status)
          ]}
        />
      </div>
      <Panel title="Market developments">
        <Status {...state} />
        {state.data?.items.length ? (
          <EventList
            events={state.data.items}
            busy={busy}
            ack={(id) =>
              void act(
                id,
                () => write(`/events/${encodeURIComponent(id)}/ack`),
                () => {
                  void state.reload()
                  notify('Event acknowledged.')
                }
              )
            }
          />
        ) : (
          !state.loading &&
          !state.error && (
            <Empty href="/settings" label="Review collection sources">
              No events match these filters.
            </Empty>
          )
        )}
      </Panel>
      <ComparisonsPanel act={act} busy={busy} notify={notify} />
      <Stamp updated={state.updated} />
    </>
  )
}

function ComparisonsPanel({
  act,
  busy,
  notify,
  initialId = ''
}: {
  act: Action
  busy: string | null
  notify: (value: string) => void
  initialId?: string
}) {
  const comparisons = useMarket<List<Comparison>>('/comparisons')
  const facts = useMarket<List<Fact>>('/facts?limit=500')
  const [oldId, setOldId] = useState(initialId),
    [newId, setNewId] = useState('')
  useEffect(() => {
    if (initialId) setOldId(initialId)
  }, [initialId])
  return (
    <section id="comparison" aria-label="Compare saved observations">
      <Panel
        title="Period comparisons"
        subtitle="Select saved observations to check eligibility. Pending review, incompatible definitions or units will return a blocked comparison with reasons."
      >
        <Status {...facts} />
        <div className="flex flex-wrap items-end gap-4 border-b border-slate-100 p-5">
          {[
            { label: 'Earlier observation', value: oldId, set: setOldId },
            { label: 'Later observation', value: newId, set: setNewId }
          ].map((field) => (
            <label
              key={field.label}
              className="min-w-48 flex-1 text-xs text-slate-600"
            >
              {field.label}
              <select
                value={field.value}
                onChange={(e) => field.set(e.target.value)}
                className={cn(inputClass, 'mt-2')}
              >
                <option value="">Select saved observation</option>
                {facts.data?.items.map((f) => (
                  <option key={f.id} value={f.id}>
                    {human(f.metric)} · {f.geography} ·{' '}
                    {f.period || 'Period unknown'} · {f.value} {f.unit} ·{' '}
                    {human(f.status)}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <Button
            className={actionClass}
            disabled={!!busy || !oldId || !newId || oldId === newId}
            onClick={() =>
              void act(
                'compare',
                () =>
                  write<Comparison>('/compare', {
                    old_id: oldId,
                    new_id: newId
                  }),
                (c) => {
                  notify(
                    c.reasons?.join('; ') ||
                      c.reason ||
                      `Comparison ${human(c.status)}.`
                  )
                  void comparisons.reload()
                }
              )
            }
          >
            Compare observations
          </Button>
        </div>
        <Status {...comparisons} />
        {comparisons.data?.items.length ? (
          <div className="divide-y divide-slate-100">
            {comparisons.data.items.map((c, i) => (
              <div
                key={c.id || i}
                className="flex flex-wrap items-center justify-between gap-3 p-5 text-sm"
              >
                <div>
                  <p className="font-medium">
                    {human(c.metric || c.new?.metric)} ·{' '}
                    {human(c.geography || c.new?.geography)}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {c.reasons?.join('; ') ||
                      c.reason ||
                      'See the linked observations for definitions and evidence.'}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="tabular-nums">
                    Delta:{' '}
                    {c.absolute_change ??
                      c.delta ??
                      'Not eligible / not available'}{' '}
                    {c.change_unit}
                  </span>
                  <Badge value={c.status} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Empty href="/market-data" label="Inspect available observations">
            No comparison checks recorded yet. Inspect evidence first; this
            interface does not approve observations.
          </Empty>
        )}
      </Panel>
    </section>
  )
}

function SourceHealth({
  state,
  refresh,
  busy
}: {
  state: ReturnType<typeof useMarket<List<Source>>>
  refresh: (id?: string) => void
  busy: string | null
}) {
  return (
    <Panel
      title="Source health"
      subtitle="Collection status reflects the last real attempt; a refresh queues a background job."
      action={
        <button
          className="text-xs font-medium text-teal-800"
          onClick={() => void state.reload()}
        >
          Check health
        </button>
      }
    >
      <Status {...state} />
      {state.data?.items.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                {[
                  'Source',
                  'Collection',
                  'Health',
                  'Last success',
                  'Action'
                ].map((h) => (
                  <th className="px-5 py-3 font-medium" scope="col" key={h}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {state.data.items.map((s) => (
                <tr key={s.id}>
                  <td className="px-5 py-3">
                    <a
                      className="font-medium text-slate-800 hover:text-teal-800"
                      href={externalUrl(s.url)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {s.name} ↗
                    </a>
                    {s.last_error && (
                      <p className="mt-1 max-w-md text-red-700">
                        {s.last_error}
                      </p>
                    )}
                  </td>
                  <td className="px-5 py-3">
                    {s.enabled ? 'Enabled' : 'Paused'}
                  </td>
                  <td className="px-5 py-3">
                    <Badge value={s.health} />
                  </td>
                  <td className="whitespace-nowrap px-5 py-3 tabular-nums">
                    {time(s.last_success)}
                  </td>
                  <td className="px-5 py-3">
                    <Button
                      size="sm"
                      disabled={!!busy || !s.enabled}
                      className="border border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                      onClick={() => refresh(s.id)}
                    >
                      <RefreshCw className="size-3" />
                      {busy === s.id ? 'Starting…' : 'Refresh'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !state.loading &&
        !state.error && (
          <Empty href="/settings" label="Open monitor settings">
            No source catalog is available.
          </Empty>
        )
      )}
    </Panel>
  )
}

function EvidenceDrawer({
  id,
  close
}: {
  id: string | null
  close: () => void
}) {
  const params = useSearchParams()
  const state = useMarket<Evidence>(
    id ? `/facts/${encodeURIComponent(id)}/evidence` : null
  )
  const e = state.data
  const [reviewer, setReviewer] = useState('')
  const [note, setNote] = useState('')
  const [reviewBusy, setReviewBusy] = useState<ReviewDecision | null>(null)
  const [reviewError, setReviewError] = useState('')
  const [reviewMessage, setReviewMessage] = useState('')
  useEffect(() => {
    setReviewer(window.localStorage.getItem('market-reviewer') || '')
  }, [])
  useEffect(() => {
    setNote('')
    setReviewError('')
    setReviewMessage('')
  }, [id])
  const submit = async (decision: ReviewDecision) => {
    if (!e) return
    const name = reviewer.trim()
    if (name.length < 2) {
      setReviewError(
        'Enter your name (at least 2 characters) so the decision is attributable.'
      )
      return
    }
    if (decision === 'reject' && note.trim().length < 3) {
      setReviewError('A rejection needs a short reason.')
      return
    }
    setReviewBusy(decision)
    setReviewError('')
    setReviewMessage('')
    try {
      await reviewFact(e.fact.id, decision, name, note.trim())
      window.localStorage.setItem('market-reviewer', name)
      setReviewMessage(`Recorded: ${decision} by ${name}.`)
      setNote('')
      await state.reload()
      window.dispatchEvent(new Event('market:refresh'))
    } catch (error) {
      setReviewError(
        error instanceof Error ? error.message : 'The review request failed.'
      )
    } finally {
      setReviewBusy(null)
    }
  }
  return (
    <Dialog
      open={!!id}
      onOpenChange={(open) => {
        if (!open) close()
      }}
    >
      <DialogContent className="left-auto right-0 top-0 h-dvh max-h-dvh w-full max-w-xl translate-x-0 translate-y-0 rounded-none border-slate-200 bg-white p-6 text-slate-900">
        <DialogTitle className="text-balance pr-8 text-xl">
          Observation evidence
        </DialogTitle>
        <DialogDescription className="mt-2 text-sm text-slate-500">
          Original source, exact quote, and provenance for this observation.
        </DialogDescription>
        <Status {...state} />
        {e && (
          <div className="mt-6 space-y-6">
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-xs text-slate-500">
                {human(e.fact.metric)} · {e.fact.geography} ·{' '}
                {e.fact.period || 'Period unknown'}
              </p>
              <p className="my-3 text-2xl font-semibold tabular-nums">
                {e.fact.value ?? 'Unknown'} {e.fact.unit}
              </p>
              <Badge value={e.fact.status} />
              <p className="mt-3 text-sm text-slate-700">
                {reviewMeaning(e.fact.status, e.fact.human_review_status)}
              </p>
              <p className="mt-3 text-sm text-slate-600">
                {e.fact.definition || 'Definition not supplied by the source.'}
              </p>
              {e.fact.issues?.length ? (
                <div className="mt-3 rounded-md border border-slate-200 bg-white p-3">
                  <p className="text-xs font-semibold text-slate-700">
                    Review flags
                  </p>
                  <ul className="mt-2 list-inside list-disc text-xs leading-6 text-slate-600">
                    {e.fact.issues.map((issue) => (
                      <li key={issue}>{human(issue).toLowerCase()}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
            <section>
              <h3 className="text-sm font-semibold">Source quotation</h3>
              <blockquote className="mt-3 text-pretty border-l-2 border-teal-700 pl-4 text-sm leading-7 text-slate-700">
                {e.evidence.quote ||
                  'No quotation available. This observation requires evidence review.'}
              </blockquote>
              <p className="mt-3 text-xs text-slate-500">
                Page {e.evidence.page ?? 'not specified'} ·{' '}
                {human(e.evidence.locator)}
              </p>
            </section>
            <section className="space-y-3 text-sm">
              <h3 className="font-semibold">
                {e.document.title || 'Original document'}
              </h3>
              <p className="text-xs text-slate-500">
                Published {time(e.document.published_at)}
                <br />
                Collected {time(e.document.collected_at)}
              </p>
              <p className="text-xs text-slate-500">
                Reporting period: {e.fact.period || 'Not supplied'}. Collection
                time is not the date of the market observation.
              </p>
              <details className="text-xs text-slate-500">
                <summary>Technical provenance</summary>
                <p className="mt-2 break-all font-mono">
                  SHA-256: {e.document.sha256 || 'Not available'}
                </p>
                <p className="text-xs text-slate-500">
                  Method: {human(e.fact.method)} · Grade: {human(e.fact.grade)}
                  <br />
                  Run: {human(e.fact.run_id)}
                </p>
              </details>
              <div className="flex flex-wrap gap-4">
                {externalUrl(e.document.url) && (
                  <a
                    className="text-teal-800 underline"
                    href={externalUrl(e.document.url)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Publisher page ↗
                  </a>
                )}
                <a
                  className="inline-flex items-center gap-2 text-teal-800 underline"
                  href={
                    fileUrl(e.download_url) ||
                    `${MARKET_API}/documents/${encodeURIComponent(e.document.id)}/file`
                  }
                  target="_blank"
                  rel="noreferrer"
                >
                  <ArrowDownToLine className="size-4" />
                  Original file
                </a>
              </div>
            </section>
            <section className="space-y-3 border-t border-slate-200 pt-4 text-sm">
              <h3 className="font-semibold">Human review</h3>
              <p className="text-slate-600">
                Approving records your name against a snapshot of this
                observation and lets it be used in comparisons. Reading the
                original does not change review status on its own.
              </p>
              {e.approval?.blockers?.length ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  <p className="font-semibold">Open before approval</p>
                  <ul className="mt-1 list-inside list-disc leading-6">
                    {e.approval.blockers.map((b) => (
                      <li key={b}>{human(b).toLowerCase()}</li>
                    ))}
                  </ul>
                  <p className="mt-1">
                    A note is required to approve a flagged observation.
                  </p>
                </div>
              ) : null}
              <label className="block text-xs font-medium text-slate-600">
                Reviewer
                <input
                  className={`${inputClass} mt-1`}
                  value={reviewer}
                  onChange={(event) => setReviewer(event.target.value)}
                  placeholder="Your name"
                  maxLength={80}
                />
              </label>
              <label className="block text-xs font-medium text-slate-600">
                Note
                <textarea
                  className="mt-1 min-h-20 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-100"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="What did you check, and what remains uncertain?"
                  maxLength={1000}
                />
              </label>
              {reviewError ? (
                <p className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-800">
                  {reviewError}
                </p>
              ) : null}
              {reviewMessage ? (
                <p className="rounded-md border border-teal-200 bg-teal-50 p-2 text-xs text-teal-900">
                  {reviewMessage}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  disabled={!!reviewBusy || !e.approval?.eligible}
                  onClick={() => void submit('approve')}
                >
                  {reviewBusy === 'approve' ? 'Approving…' : 'Approve'}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!!reviewBusy}
                  onClick={() => void submit('reject')}
                >
                  {reviewBusy === 'reject' ? 'Rejecting…' : 'Reject'}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!!reviewBusy || e.fact.status === 'pending_review'}
                  onClick={() => void submit('reopen')}
                >
                  {reviewBusy === 'reopen' ? 'Reopening…' : 'Reopen'}
                </Button>
              </div>
              {e.reviews?.length ? (
                <div className="rounded-md border border-slate-200 p-3">
                  <p className="text-xs font-semibold text-slate-700">
                    Decision history
                  </p>
                  <ul className="mt-2 space-y-2 text-xs text-slate-600">
                    {[...e.reviews]
                      .sort((a, b) =>
                        String(b.at || b.created_at).localeCompare(
                          String(a.at || a.created_at)
                        )
                      )
                      .map((r) => (
                        <li key={r.id}>
                          <span className="font-medium text-slate-800">
                            {human(r.decision)}
                          </span>{' '}
                          · {r.reviewer} · {time(r.at || r.created_at)}
                          {r.note ? (
                            <span className="block leading-5">{r.note}</span>
                          ) : null}
                        </li>
                      ))}
                  </ul>
                </div>
              ) : null}
              <div className="flex flex-wrap gap-4 border-t border-slate-200 pt-3">
                <Link
                  className="text-teal-800 underline"
                  href={researchLink('fact', e.fact.id, params.toString())}
                >
                  Analyze with AI
                </Link>
                <Link
                  className="text-teal-800 underline"
                  href={`/market-data?compare=${encodeURIComponent(e.fact.id)}#comparison`}
                >
                  Check comparison eligibility
                </Link>
              </div>
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function JobsPage({
  act,
  busy,
  notify
}: {
  act: Action
  busy: string | null
  notify: (value: string) => void
}) {
  const [polling, setPolling] = useState(true)
  const state = useMarket<List<Job>>('/jobs', polling ? 5000 : 0)
  return (
    <>
      <Panel
        title="Collection & processing jobs"
        subtitle="Read-only polling every 5 seconds while visible, for up to 10 minutes. Refresh the page to resume."
        action={
          <div className="flex gap-3">
            <button
              className="text-xs text-slate-600"
              onClick={() => setPolling(!polling)}
            >
              {polling ? 'Pause polling' : 'Resume polling'}
            </button>
            <Button className={actionClass} onClick={() => void state.reload()}>
              <RefreshCw className="size-4" />
              Reload
            </Button>
          </div>
        }
      >
        <Status {...state} />
        {state.data?.items.length ? (
          <div className="divide-y divide-slate-100">
            {state.data.items.map((j) => {
              const presentation = jobPresentation(j)
              return (
                <article key={j.id} className="space-y-3 p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold">
                        {presentation.title}
                      </h3>
                    </div>
                    <Badge value={j.status} />
                  </div>
                  <p className="text-sm text-slate-600">
                    {presentation.explanation}
                  </p>
                  {presentation.showProgress && (
                    <>
                      <div className="flex items-center justify-between gap-3 text-xs text-slate-600">
                        <span>Stage: {human(j.stage)}</span>
                        <span className="tabular-nums">
                          {presentation.progress == null
                            ? 'Completion time is not estimated'
                            : `${Math.round(presentation.progress)}% of processing stages`}
                        </span>
                      </div>
                      <progress
                        className="h-2 w-full accent-teal-800"
                        aria-label={`${j.kind} progress`}
                        max={100}
                        value={presentation.progress}
                      />
                    </>
                  )}
                  {presentation.href && (
                    <Link
                      className="inline-block text-sm font-medium text-teal-800 underline"
                      href={presentation.href}
                    >
                      {presentation.linkLabel}
                    </Link>
                  )}
                  <div className="flex flex-wrap justify-between gap-3 text-xs text-slate-500">
                    <span>
                      Started {time(j.started_at)} · Finished{' '}
                      {time(j.finished_at)} · Attempt{' '}
                      {j.attempts ?? 'not recorded'}
                    </span>
                    {retryableJob(j) && (
                      <Button
                        disabled={!!busy}
                        className={actionClass}
                        onClick={() =>
                          void act(
                            j.id,
                            () =>
                              write<Job>(
                                `/jobs/${encodeURIComponent(j.id)}/retry`
                              ),
                            (next) => {
                              notify(`Retry job ${next.id} accepted.`)
                              void state.reload()
                            }
                          )
                        }
                      >
                        Retry job
                      </Button>
                    )}
                    {['failed', 'error', 'cancelled'].includes(j.status) &&
                      ['ask', 'report', 'report_analysis'].includes(j.kind) && (
                        <Link
                          href={j.kind === 'ask' ? '/ask' : '/reports'}
                          className="font-medium text-teal-800 underline"
                        >
                          {j.kind === 'ask'
                            ? 'Review question in saved-record research'
                            : 'Retry from Reports'}
                        </Link>
                      )}
                  </div>
                  {j.error && (
                    <p
                      role="alert"
                      className="rounded-md bg-red-50 p-3 text-sm text-red-800"
                    >
                      {j.error}
                    </p>
                  )}
                  {j.plan && (
                    <details className="rounded-md border border-slate-200 p-3 text-xs text-slate-600">
                      <summary className="cursor-pointer font-medium">
                        Research plan and checkpoints
                      </summary>
                      <p className="mt-2">
                        {j.plan.scope.geographies.join(', ')} ·{' '}
                        {j.plan.scope.metrics.join(', ')} ·{' '}
                        {j.plan.scope.requested_periods?.length
                          ? j.plan.scope.requested_periods.join(', ')
                          : j.plan.scope.observation_period || 'Period unknown'}
                      </p>
                      <p>
                        Decision: {human(j.plan.decision)} ·{' '}
                        {j.plan.next_checks.length} next checks
                      </p>
                      {j.plan.adaptation && (
                        <p>
                          Saved-document follow-up: {j.plan.adaptation.passes}{' '}
                          pass · {j.plan.adaptation.missing_cells} missing cells
                          · {j.plan.adaptation.deferred_cells} deferred ·
                          maximum {j.plan.adaptation.limit} branches. Document
                          leads do not fill verified coverage.
                        </p>
                      )}
                      <ul className="mt-2 space-y-1">
                        {j.plan.nodes.map((node) => {
                          const checkpoint = j.checkpoints?.[node.id]
                          return (
                            <li key={node.id}>
                              {node.id}: {human(node.status)} (
                              {node.required ? 'required' : 'optional'})
                              {checkpoint?.reused
                                ? ' · valid checkpoint reused'
                                : ''}
                              {checkpoint?.elapsed_ms != null
                                ? ` · ${checkpoint.elapsed_ms} ms`
                                : ''}
                            </li>
                          )
                        })}
                      </ul>
                    </details>
                  )}
                  <details className="break-all text-xs text-slate-500">
                    <summary>Audit details</summary>Task: {j.id}
                    <br />
                    Execution: {j.run_id || 'Not supplied'}
                  </details>
                </article>
              )
            })}
          </div>
        ) : (
          !state.loading &&
          !state.error && (
            <Empty href="/settings" label="Review collection settings">
              No jobs yet. Use Refresh sources to start collecting.
            </Empty>
          )
        )}
      </Panel>
      <Stamp updated={state.updated} />
    </>
  )
}

function ReportsPage({
  act,
  busy,
  notify,
  runtimeMode
}: {
  act: Action
  busy: string | null
  notify: (value: string) => void
  runtimeMode?: 'live' | 'mock'
}) {
  const state = useMarket<List<Report>>('/reports')
  const preferences = useMarket<Settings>('/settings')
  const params = useSearchParams()
  const reportId = params.get('report')
  const opened = useRef('')
  const readSequence = useRef(0)
  const [showSuperseded, setShowSuperseded] = useState(false)
  const [selected, setSelected] = useState<Report | null>(null)
  const [content, setContent] = useState('')
  const [readError, setReadError] = useState('')
  const [reading, setReading] = useState(false)
  const read = useCallback(async (report: Report) => {
    const sequence = ++readSequence.current
    setSelected(report)
    setContent('')
    setReadError('')
    setReading(true)
    try {
      const response = await fetch(
        `${MARKET_API}/reports/${encodeURIComponent(report.id)}?format=markdown`
      )
      if (!response.ok)
        throw new Error(
          'Report could not be loaded. Download the original or retry.'
        )
      const text = await response.text()
      if (sequence === readSequence.current) setContent(text)
    } catch (e) {
      if (sequence === readSequence.current)
        setReadError(e instanceof Error ? e.message : 'Could not load report')
    } finally {
      if (sequence === readSequence.current) setReading(false)
    }
  }, [])
  useEffect(() => {
    const report = state.data?.items.find((item) => item.id === reportId)
    if (report && opened.current !== report.id) {
      opened.current = report.id
      void read(report)
    }
  }, [reportId, state.data, read])
  return (
    <>
      {reportId &&
        state.data &&
        !state.data.items.some((r) => r.id === reportId) && (
          <p role="alert">
            The linked report is not available in the saved record. No
            replacement report was generated.
          </p>
        )}
      <Panel
        title="Create a market briefing"
        subtitle="Daily and weekly briefings use deterministic saved records. Optional AI weekly analysis calls the configured model and remains REVIEW_REQUIRED."
      >
        <div className="flex flex-wrap items-center justify-between gap-4 p-5">
          <p className="max-w-xl text-pretty text-sm leading-6 text-slate-600">
            Reports preserve source citations and review labels. Choose a period
            to generate a new dated briefing.
          </p>
          <div className="flex flex-wrap gap-3">
            {['daily', 'weekly'].map((period) => (
              <Button
                className={actionClass}
                key={period}
                disabled={!!busy}
                onClick={() =>
                  void act(
                    `report-${period}`,
                    () =>
                      write<Report>('/reports', {
                        period,
                        include_analysis: false
                      }),
                    (r) => {
                      notify(`${r.title} generated.`)
                      void state.reload()
                      void read(r)
                    }
                  )
                }
              >
                {busy === `report-${period}`
                  ? 'Generating…'
                  : `Generate ${period}`}
              </Button>
            ))}
            <Button
              className={actionClass}
              disabled={!!busy}
              onClick={() =>
                void act(
                  'report-monthly',
                  async () => {
                    const response = await fetch(
                      `${new URL(MARKET_API).origin}/report`,
                      {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: '{}'
                      }
                    )
                    if (!response.ok)
                      throw new Error('Monthly report generation failed')
                    const payload = await response.json()
                    return {
                      id: payload.report_id,
                      title: 'Monthly monitoring brief',
                      created_at: payload.as_of || new Date().toISOString(),
                      period: 'monthly'
                    } as Report
                  },
                  (r) => {
                    notify(
                      'Monthly monitoring brief generated from saved evidence.'
                    )
                    void state.reload()
                    void read(r)
                  }
                )
              }
            >
              {busy === 'report-monthly' ? 'Generating…' : 'Generate monthly'}
            </Button>
            <Button
              className="border border-teal-800 bg-white text-teal-800 hover:bg-teal-50"
              disabled={!!busy || runtimeMode === 'mock'}
              title={
                runtimeMode === 'mock'
                  ? 'Provider-backed analysis is disabled in mock mode.'
                  : undefined
              }
              onClick={() =>
                void act(
                  'report-ai-weekly',
                  () =>
                    write<Job>('/reports', {
                      period: 'weekly',
                      include_analysis: true
                    }),
                  (job) =>
                    notify(
                      `AI weekly analysis queued as job ${job.id} (${human(job.status)}). Model-generated analysis requires review; follow progress in Job Status.`
                    )
                )
              }
            >
              {busy === 'report-ai-weekly'
                ? 'Queuing…'
                : runtimeMode === 'mock'
                  ? 'AI weekly disabled in mock'
                  : 'Generate AI weekly (model)'}
            </Button>
          </div>
        </div>
      </Panel>
      <Panel title="Saved reports">
        <div className="space-y-2 border-b border-slate-100 p-4 text-sm text-slate-600">
          <p>
            Daily/weekly describes briefing cadence. Exact statistical coverage
            dates are not supplied by the report list; inspect each
            observation&apos;s period inside the report. Generating a report
            does not approve its evidence.
          </p>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={showSuperseded}
              onChange={(e) => setShowSuperseded(e.target.checked)}
            />
            Show superseded versions
          </label>
        </div>
        <Status {...state} />
        {state.data?.items.length ? (
          <div className="divide-y divide-slate-100">
            {state.data.items
              .filter((r) => showSuperseded || r.status !== 'superseded')
              .map((r) => (
                <article
                  className="flex flex-wrap items-center justify-between gap-4 p-5"
                  key={r.id}
                >
                  <div>
                    <h3 className="text-sm font-semibold">{r.title}</h3>
                    <p className="mt-2 text-xs text-slate-500">
                      {human(r.period)} · Created {time(r.created_at)}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {r.status === 'superseded'
                        ? 'Superseded · retained for audit'
                        : 'Saved briefing · evidence review labels remain in force'}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-4 text-xs">
                    {r.generation_status && (
                      <Badge value={r.generation_status} />
                    )}
                    <button
                      className="font-medium text-teal-800 underline"
                      onClick={() => void read(r)}
                    >
                      Read report
                    </button>
                    <Link
                      className="text-teal-800 underline"
                      href={researchLink('report', r.id, params.toString())}
                    >
                      Continue with AI
                    </Link>
                    <Link
                      className="text-teal-800 underline"
                      href={`/settings?report=${encodeURIComponent(r.id)}`}
                    >
                      Review monitoring
                    </Link>
                    <a
                      className="text-teal-800 underline"
                      target="_blank"
                      rel="noreferrer"
                      href={`${MARKET_API}/reports/${encodeURIComponent(r.id)}?format=html`}
                    >
                      Download HTML
                    </a>
                    <a
                      className="text-teal-800 underline"
                      href={`${MARKET_API}/reports/${encodeURIComponent(r.id)}?format=markdown`}
                      download
                    >
                      Download Markdown
                    </a>
                    <Button
                      disabled={
                        !!busy ||
                        !preferences.data?.notification_configured ||
                        !preferences.data?.notifications_enabled
                      }
                      className="border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                      onClick={() =>
                        void act(
                          `notify-${r.id}`,
                          () =>
                            write<{
                              status: string
                              error?: string
                              detail?: string
                            }>('/notifications', { report_id: r.id }),
                          (result) =>
                            notify(
                              result.status === 'configuration_missing'
                                ? 'Notification not sent: server notification credentials are not configured. Configure them on the server, then retry.'
                                : `Notification ${human(result.status)}. ${result.error || result.detail || ''}`
                            )
                        )
                      }
                    >
                      {preferences.data?.notification_configured &&
                      preferences.data?.notifications_enabled
                        ? 'Send notification'
                        : 'Notifications unavailable'}
                    </Button>
                    {(!preferences.data?.notification_configured ||
                      !preferences.data?.notifications_enabled) && (
                      <Link
                        href="/settings"
                        className="text-teal-800 underline"
                      >
                        Review notification setup
                      </Link>
                    )}
                  </div>
                </article>
              ))}
          </div>
        ) : (
          !state.loading &&
          !state.error && (
            <Empty>
              No saved reports yet. Generate a daily or weekly briefing above.
            </Empty>
          )
        )}
      </Panel>
      <Stamp updated={state.updated} />
      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) {
            readSequence.current++
            setSelected(null)
          }
        }}
      >
        <DialogContent className="max-h-[90dvh] max-w-6xl border-slate-200 bg-white text-slate-900">
          <DialogTitle className="text-balance pr-6">
            {selected?.title}
          </DialogTitle>
          <DialogDescription className="mt-2 text-xs text-slate-500">
            Saved report · {time(selected?.created_at)}
          </DialogDescription>
          {selected && (
            <div className="mt-4 flex flex-wrap gap-4 text-sm">
              <Link
                className="text-teal-800 underline"
                href={researchLink('report', selected.id, params.toString())}
              >
                Continue with AI
              </Link>
              <Link
                className="text-teal-800 underline"
                href={`/settings?report=${encodeURIComponent(selected.id)}`}
              >
                Review monitoring coverage
              </Link>
              <a
                className="text-teal-800 underline"
                href={`${MARKET_API}/reports/${encodeURIComponent(selected.id)}?format=markdown`}
                download
              >
                Download this report
              </a>
            </div>
          )}
          {reading && <Skeleton className="mt-5 h-32 bg-slate-100" />}
          {readError && (
            <div role="alert" className="mt-5 text-sm text-red-800">
              {readError}
              <button
                className="ml-3 underline"
                onClick={() => selected && void read(selected)}
              >
                Retry
              </button>
            </div>
          )}
          {selected?.report_type ? (
            <div className="mt-5 max-h-[60dvh] overflow-y-auto">
              <SavedReport reportId={selected.id} />
            </div>
          ) : (
            <div className="market-markdown mt-5 break-words text-sm leading-7 text-slate-700">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ children }) => (
                    <div className="my-4 overflow-x-auto">
                      <table className="w-full min-w-max border-collapse text-left text-xs">
                        {children}
                      </table>
                    </div>
                  )
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

function SettingsPage({
  act,
  busy,
  notify
}: {
  act: Action
  busy: string | null
  notify: (value: string) => void
}) {
  const state = useMarket<Settings>('/settings')
  const params = useSearchParams()
  const linkedReport = params.get('report')
  const reports = useMarket<List<Report>>(linkedReport ? '/reports' : null)
  const report = reports.data?.items.find((item) => item.id === linkedReport)
  return (
    <>
      {linkedReport && (
        <section className="rounded-xl border border-slate-200 bg-white p-5 text-sm">
          <h2 className="font-semibold">Monitoring after a briefing</h2>
          <p className="mt-2">
            {report
              ? `${report.title} · Generated ${time(report.created_at)}`
              : reports.loading
                ? 'Loading the linked report…'
                : 'The linked report could not be found.'}
          </p>
          <p className="mt-2">
            Review the existing workspace coverage below. No setting has been
            changed by opening this page. The service supports workspace
            monitoring; a report-specific subscription is not available.
          </p>
          {report && (
            <Link
              className="mt-3 inline-block text-teal-800 underline"
              href={`/reports?report=${encodeURIComponent(report.id)}`}
            >
              Return to this report
            </Link>
          )}
        </section>
      )}
      <div className="flex flex-wrap gap-4 text-sm">
        <Link className="text-teal-800 underline" href="/jobs">
          View collection and report results
        </Link>
        <Link className="text-teal-800 underline" href="/events">
          Inspect market developments
        </Link>
      </div>
      <Panel
        title="Collection preferences"
        subtitle="Provider secrets are managed on the server. This form only saves operational preferences."
      >
        <Status {...state} />
        {state.data && (
          <SettingsForm
            key={state.updated}
            settings={state.data}
            busy={busy}
            save={(values) =>
              void act(
                'settings',
                () => write<Settings>('/settings', values, 'PUT'),
                () => {
                  notify('Monitor preferences saved.')
                  void state.reload()
                }
              )
            }
          />
        )}
      </Panel>
      <Panel
        title="Scheduled collection"
        subtitle="Schedule state comes from the service."
      >
        {state.data?.schedules?.length ? (
          <div className="divide-y divide-slate-100">
            {state.data.schedules.map((s, i) => (
              <div key={i} className="flex justify-between gap-4 p-5 text-sm">
                <span>
                  {(
                    {
                      'london-report-weekly': 'Weekly market briefing',
                      'london-report-daily': 'Daily market briefing',
                      'london-market': 'Market source collection',
                      'london-news': 'News collection'
                    } as Record<string, string>
                  )[s.name || ''] || human(s.name || s.kind)}
                  {s.cron_expr && (
                    <details className="mt-2 text-xs text-slate-500">
                      <summary>Schedule details</summary>
                      <p>
                        Expression: {s.cron_expr}. Service schedule timezone is
                        not supplied by this endpoint; use the next-run
                        timestamp shown here.
                      </p>
                    </details>
                  )}
                </span>
                <span className="text-slate-500">
                  {s.enabled === false
                    ? 'Paused'
                    : `Next run ${time(typeof s.next_run_at === 'number' ? s.next_run_at * 1000 : s.next_run_at)} (${Intl.DateTimeFormat().resolvedOptions().timeZone})`}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <Empty>
            No schedule receipts are available yet. Save preferences and check
            Job Status for actual work.
          </Empty>
        )}
      </Panel>
      <IndicatorCoverage />
      <Stamp updated={state.updated} />
    </>
  )
}
function SettingsForm({
  settings,
  busy,
  save
}: {
  settings: Settings
  busy: string | null
  save: (values: unknown) => void
}) {
  const [news, setNews] = useState(settings.news_interval_hours),
    [market, setMarket] = useState(settings.market_interval_hours),
    [geo, setGeo] = useState(settings.geographies),
    [metrics, setMetrics] = useState(settings.metrics),
    [notifications, setNotifications] = useState(
      settings.notifications_enabled
    ),
    [monitoring, setMonitoring] = useState(settings.monitoring_enabled ?? true),
    [monitorAnalysis, setMonitorAnalysis] = useState(
      settings.monitor_analysis_enabled ?? false
    ),
    [rentThreshold, setRentThreshold] = useState(
      settings.rent_threshold_pct ?? 5
    ),
    [takeupThreshold, setTakeupThreshold] = useState(
      settings.takeup_threshold_pct ?? 10
    ),
    [vacancyThreshold, setVacancyThreshold] = useState(
      settings.vacancy_threshold_pp ?? 0.5
    )
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!geo.length || !metrics.length) return
    save({
      news_interval_hours: news,
      market_interval_hours: market,
      notifications_enabled: notifications,
      monitoring_enabled: monitoring,
      monitor_analysis_enabled: monitorAnalysis,
      rent_threshold_pct: rentThreshold,
      takeup_threshold_pct: takeupThreshold,
      vacancy_threshold_pp: vacancyThreshold,
      geographies: geo,
      metrics
    })
  }
  const catalog = useMarket<List<Fact>>('/facts?limit=500')
  return (
    <form className="space-y-6 p-5" onSubmit={submit}>
      <p className="text-xs text-slate-500">
        Supported collection intervals: 1, 2, 3, 4, 6, 8, 12, 24 or 168 hours.
      </p>
      <div className="grid gap-5 sm:grid-cols-2">
        <label className="text-sm font-medium">
          News interval (hours)
          <select
            className={cn(inputClass, 'mt-2')}
            required
            value={news}
            onChange={(e) => setNews(Number(e.target.value))}
          >
            {[1, 2, 3, 4, 6, 8, 12, 24, 168].map((hours) => (
              <option key={hours} value={hours}>
                {hours} hours
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          Market data interval (hours)
          <select
            className={cn(inputClass, 'mt-2')}
            required
            value={market}
            onChange={(e) => setMarket(Number(e.target.value))}
          >
            {[1, 2, 3, 4, 6, 8, 12, 24, 168].map((hours) => (
              <option key={hours} value={hours}>
                {hours} hours
              </option>
            ))}
          </select>
        </label>
        <CoveragePicker
          label="Geographies"
          selected={geo}
          options={(catalog.data?.items || []).map((f) => f.geography)}
          onChange={setGeo}
        />
        <CoveragePicker
          label="Metrics"
          selected={metrics}
          options={(catalog.data?.items || []).map((f) => f.metric)}
          onChange={setMetrics}
        />
      </div>
      <fieldset className="rounded-lg border border-slate-200 p-4">
        <legend className="px-2 text-sm font-medium">
          Change alert thresholds
        </legend>
        <p className="mb-4 text-xs text-slate-500">
          Positive thresholds up to 1,000. Rent and take-up use percent change;
          vacancy uses percentage points. Alerts require reviewed, compatible
          observations in the selected coverage. A threshold does not make
          unreviewed inputs eligible for calculation.
        </p>
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            {
              label: 'Rent change (%)',
              value: rentThreshold,
              set: setRentThreshold
            },
            {
              label: 'Take-up change (%)',
              value: takeupThreshold,
              set: setTakeupThreshold
            },
            {
              label: 'Vacancy change (pp)',
              value: vacancyThreshold,
              set: setVacancyThreshold
            }
          ].map((field) => (
            <label
              key={field.label}
              className="text-xs font-medium text-slate-600"
            >
              {field.label}
              <input
                className={cn(inputClass, 'mt-2')}
                type="number"
                min="0.000001"
                max="1000"
                step="any"
                required
                value={field.value}
                onChange={(e) => field.set(Number(e.target.value))}
              />
            </label>
          ))}
        </div>
      </fieldset>
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <label className="mb-4 flex items-center gap-3 text-sm font-medium">
          <input
            className="size-4 accent-teal-800"
            type="checkbox"
            checked={monitoring}
            onChange={(e) => setMonitoring(e.target.checked)}
          />
          Enable scheduled collection
        </label>
        <label className="flex items-center gap-3 text-sm font-medium">
          <input
            className="size-4 accent-teal-800"
            type="checkbox"
            checked={notifications}
            onChange={(e) => setNotifications(e.target.checked)}
          />
          Enable report notifications
        </label>
        <label className="mt-4 flex items-center gap-3 text-sm font-medium">
          <input
            className="size-4 accent-teal-800"
            type="checkbox"
            checked={monitorAnalysis}
            onChange={(e) => setMonitorAnalysis(e.target.checked)}
            aria-describedby="monitor-analysis-help"
          />
          Analyze detected changes with the configured model
        </label>
        <p id="monitor-analysis-help" className="mt-2 text-xs text-slate-600">
          Off by default. Enabling permits bounded model calls for new eligible
          change events. Only interpretations that pass publication checks can
          trigger notifications; failed analysis is retained without automatic
          model retries.
        </p>
        <p className="mt-3 text-xs text-slate-600">
          Server configuration:{' '}
          {settings.notification_configured
            ? 'Configured. Delivery still requires a successful send receipt.'
            : 'Missing. Notifications cannot be sent until server credentials are configured.'}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Configure{' '}
          <code className="rounded bg-slate-100 px-1">
            LONDON_NOTIFICATION_URL
          </code>{' '}
          as an Apprise URL, e.g.{' '}
          <code className="rounded bg-slate-100 px-1">
            json://https://hooks.example.com/xxx
          </code>
          ,{' '}
          <code className="rounded bg-slate-100 px-1">
            mailto://user:pass@host
          </code>
          ,{' '}
          <code className="rounded bg-slate-100 px-1">
            slack://tokenA/tokenB/tokenC
          </code>
          .
        </p>
      </div>
      <Button
        type="submit"
        disabled={!!busy || !geo.length || !metrics.length}
        className={actionClass}
      >
        {busy === 'settings' ? 'Saving…' : 'Save monitor settings'}
      </Button>
    </form>
  )
}

type ChatEntry = {
  question: string
  answer: string
  mode: string
  resolved_mode?: 'saved' | 'agent' | 'research'
  citations: {
    fact_id?: string
    id?: string
    title?: string
    url?: string
    source_id?: string
    document_id?: string
    period?: string
  }[]
  error?: string
  run_id?: string
  submission_id?: string
  research_job_id?: string
  skill_calls?: { skill: string; datasource: string }[]
  as_of?: string | null
  disclaimer?: string
  first_content_at?: number
  completed_at?: number
  created: number
  report?: ReportArtifact
  progress?: string
}
function AskPage({
  evidence,
  runtimeMode
}: {
  evidence: (id: string) => void
  runtimeMode?: 'live' | 'mock'
}) {
  const params = useSearchParams()
  const [refreshSources, setRefreshSources] = useState(false)
  const [researchBusy, setResearchBusy] = useState(false)
  const [researchJobId, setResearchJobId] = useState('')
  const [researchError, setResearchError] = useState('')
  const [question, setQuestion] = useState(
      params.get('action') === 'audit'
        ? 'Perform a rigorous source and evidence audit of the previous report.'
        : ''
    ),
    [mode, setMode] = useState('auto'),
    [entries, setEntries] = useState<ChatEntry[]>([]),
    [streaming, setStreaming] = useState(false)
  const guard = useRef(false),
    controller = useRef<AbortController | null>(null)
  const researchGuard = useRef(false)
  const startResearch = async () => {
    if (researchGuard.current || !question.trim()) return
    researchGuard.current = true
    setResearchBusy(true)
    setResearchError('')
    setResearchJobId('')
    try {
      const job = await write<Job>('/research/jobs', {
        question: question.trim(),
        refresh_sources: false
      })
      setResearchJobId(job.id)
    } catch (error) {
      setResearchError(
        error instanceof Error ? error.message : 'Could not start research.'
      )
    } finally {
      researchGuard.current = false
      setResearchBusy(false)
    }
  }
  const send = async (e: FormEvent) => {
    e.preventDefault()
    if (guard.current || !question.trim()) return
    guard.current = true
    setStreaming(true)
    const selectedMode = runtimeMode === 'mock' ? 'saved' : mode
    const entry: ChatEntry = {
      question: question.trim(),
      answer: '',
      mode: selectedMode,
      citations: [],
      created: Date.now()
    }
    setEntries((prev) => [...prev, entry])
    setQuestion('')
    const update = (patch: Partial<ChatEntry>) => {
      Object.assign(entry, patch)
      setEntries((prev) =>
        prev.map((v) => (v.created === entry.created ? { ...entry } : v))
      )
    }
    controller.current = new AbortController()
    const timeout = setTimeout(() => controller.current?.abort(), 180000)
    try {
      const response = await fetch(`${MARKET_API}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': crypto.randomUUID()
        },
        body: JSON.stringify({
          message: entry.question,
          mode: selectedMode,
          refresh_sources: runtimeMode === 'mock' ? false : refreshSources,
          parent_report_id:
            [...entries].reverse().find((e) => e.report)?.report?.report_id ||
            params.get('parent_report') ||
            null
        }),
        signal: controller.current.signal
      })
      if (!response.ok) {
        const err = await response
          .json()
          .catch(() => ({ detail: response.statusText }))
        throw new Error(
          typeof err.detail === 'string' ? err.detail : 'Agent request failed'
        )
      }
      if (!response.body)
        throw new Error('The service did not return a response stream.')
      await readMarketStream(response.body, (event) => {
        if (event.type === 'progress') update({ progress: event.message })
        if (event.type === 'report')
          update({
            report: event.report,
            progress: undefined,
            first_content_at: Date.now()
          })
        if (event.type === 'token')
          update({
            answer: entry.answer + String(event.content || ''),
            first_content_at: entry.first_content_at || Date.now()
          })
        if (event.type === 'done')
          update({
            progress: undefined,
            citations: event.citations || [],
            run_id: event.run_id,
            submission_id: event.submission_id,
            research_job_id: event.research_job_id,
            skill_calls: event.skill_calls,
            as_of: event.as_of,
            disclaimer: event.disclaimer,
            resolved_mode: event.metrics?.route?.mode,
            completed_at: Date.now()
          })
      })
    } catch (error) {
      update({
        error:
          error instanceof Error && error.name === 'AbortError'
            ? 'MODEL_TIMEOUT：The browser timed out or the request was stopped. Final analysis is not confirmed complete. No automatic retry was made.'
            : error instanceof Error
              ? error.message
              : 'Unable to contact the market agent.'
      })
    } finally {
      clearTimeout(timeout)
      guard.current = false
      setStreaming(false)
    }
  }
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">
        <p className="text-pretty">
          {runtimeMode === 'mock'
            ? 'Credential-free mock mode is fail-closed: questions use only saved evidence, with no provider call or external refresh. The selected Skills and data sources appear on each answer.'
            : 'Auto sends saved-data lookups to local evidence, interpretation to the configured Agent, and explicit deep research to a background saved-evidence workflow. The selected route appears on each answer.'}
        </p>
        <Link
          href="/chat"
          className="inline-flex items-center gap-1 whitespace-nowrap font-medium underline"
        >
          DeepInsight AI & conversations <ArrowUpRight className="size-4" />
        </Link>
      </div>
      <Panel
        title="Market question"
        subtitle="Answers are based on the real service response. Review source evidence before acting."
      >
        <div className="min-h-64 space-y-6 p-5" aria-live="polite">
          {!entries.length && (
            <div className="py-8 text-center">
              <MessageSquare className="mx-auto mb-4 size-8 text-teal-800" />
              <h3 className="text-balance text-lg font-semibold">
                Start with the market record
              </h3>
              <p className="mx-auto mt-3 max-w-lg text-pretty text-sm leading-6 text-slate-500">
                Ask about a geography, metric, or reporting period. Saved mode
                returns stored observations without a model call.
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-2">
                {[
                  'What is the latest City office vacancy rate?',
                  'Show recent London office market changes.'
                ].map((text) => (
                  <button
                    key={text}
                    className="rounded-md border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:border-teal-700"
                    onClick={() => setQuestion(text)}
                  >
                    {text}
                  </button>
                ))}
              </div>
            </div>
          )}
          {entries.map((entry) => (
            <article
              key={entry.created}
              data-submission-id={entry.submission_id}
              data-first-content-ms={
                entry.first_content_at
                  ? entry.first_content_at - entry.created
                  : undefined
              }
              data-completion-ms={
                entry.completed_at
                  ? entry.completed_at - entry.created
                  : undefined
              }
              className="space-y-4 border-b border-slate-100 pb-6"
            >
              <p className="text-sm font-semibold">{entry.question}</p>
              <div className="flex items-center gap-3">
                <Badge
                  value={
                    (entry.resolved_mode || entry.mode) === 'saved'
                      ? 'deterministic saved retrieval'
                      : (entry.resolved_mode || entry.mode) === 'agent'
                        ? 'native Agent + Tools'
                        : (entry.resolved_mode || entry.mode) === 'research'
                          ? 'background saved-evidence research'
                          : 'routing question…'
                  }
                />
                <span className="text-xs text-slate-500">
                  {time(entry.created)}
                </span>
              </div>
              {entry.report && (
                <ReportView report={entry.report} evidence={evidence} />
              )}
              {entry.progress && (
                <p role="status" className="text-sm text-teal-700">
                  {entry.progress}
                </p>
              )}
              {!entry.report && (
                <div className="prose prose-sm max-w-none overflow-x-auto text-slate-700">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      table: ({ children }) => (
                        <table className="min-w-[1100px] table-auto text-left">
                          {children}
                        </table>
                      ),
                      th: ({ children }) => (
                        <th className="whitespace-nowrap p-2 align-top">
                          {children}
                        </th>
                      ),
                      td: ({ children }) => (
                        <td className="p-2 align-top">{children}</td>
                      )
                    }}
                  >
                    {entry.answer ||
                      (streaming && !entry.error
                        ? 'Waiting for service response…'
                        : 'No publishable final analysis was generated. Inspect the failure stage and reason below.')}
                  </ReactMarkdown>
                </div>
              )}
              {entry.error && (
                <p
                  role="alert"
                  className="rounded-md bg-red-50 p-3 text-sm text-red-800"
                >
                  {entry.error}
                </p>
              )}
              {entry.citations.length > 0 && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold text-slate-500">
                    SOURCES
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {entry.citations.map((citation, index) => (
                      <div
                        key={index}
                        className="rounded-md border border-slate-200 px-3 py-2 text-xs"
                      >
                        {citation.fact_id ? (
                          <button
                            className="text-teal-800 underline"
                            onClick={() => evidence(citation.fact_id!)}
                          >
                            {citation.title ||
                              citation.source_id ||
                              `Evidence ${index + 1}`}
                          </button>
                        ) : externalUrl(citation.url) ? (
                          <a
                            className="text-teal-800 underline"
                            href={externalUrl(citation.url)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {citation.title ||
                              citation.period ||
                              `Source ${index + 1}`}
                          </a>
                        ) : (
                          <span>
                            {citation.title ||
                              citation.source_id ||
                              citation.id ||
                              `Source ${index + 1}`}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {entry.run_id && (
                <p className="break-all text-xs text-slate-500">
                  Run receipt: {entry.run_id}
                </p>
              )}
              {!!entry.skill_calls?.length && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                  <p className="font-semibold text-slate-900">
                    Skills &amp; data sources
                  </p>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {entry.skill_calls.map((call) => (
                      <li
                        className="rounded-full border border-teal-200 bg-white px-2 py-1"
                        key={`${call.skill}-${call.datasource}`}
                      >
                        {call.skill} · {call.datasource}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {(entry.as_of || entry.disclaimer) && (
                <p className="text-xs leading-5 text-slate-500">
                  {entry.as_of ? `Data as of ${time(entry.as_of)}. ` : ''}
                  {entry.disclaimer}
                </p>
              )}
              {entry.research_job_id && (
                <p className="text-sm text-teal-800">
                  <Link href="/jobs" className="underline">
                    View research progress and report in Job Status (
                    {entry.research_job_id})
                  </Link>
                </p>
              )}
            </article>
          ))}
        </div>
        <form
          className="space-y-3 border-t border-slate-200 bg-slate-50 p-5"
          onSubmit={(e) => void send(e)}
        >
          <label className="sr-only" htmlFor="market-question">
            Your market question
          </label>
          <textarea
            id="market-question"
            className={cn(inputClass, 'h-24 resize-y py-3')}
            placeholder="Ask about the London office market…"
            value={question}
            maxLength={4000}
            onChange={(e) => setQuestion(e.target.value)}
            required
            disabled={streaming}
          />
          <label className="flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={refreshSources}
              disabled={streaming || runtimeMode === 'mock'}
              onChange={(e) => setRefreshSources(e.target.checked)}
            />
            {runtimeMode === 'mock'
              ? 'External source refresh is disabled in mock mode.'
              : 'Refresh enabled public sources before this answer (uses existing Jobs)'}
          </label>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-3 text-xs text-slate-600">
              Answer mode
              <select
                className={cn(inputClass, 'w-auto')}
                value={runtimeMode === 'mock' ? 'saved' : mode}
                disabled={streaming}
                onChange={(e) => setMode(e.target.value)}
              >
                {runtimeMode !== 'mock' && (
                  <option value="auto">
                    Auto · saved lookup or AI analysis
                  </option>
                )}
                <option value="saved">Saved evidence · no model</option>
                {runtimeMode !== 'mock' && (
                  <option value="agent">
                    DeepInsight AI · uses configured model
                  </option>
                )}
              </select>
            </label>
            <div className="flex gap-3">
              <Button
                type="button"
                className="border border-slate-300 bg-white text-slate-700"
                disabled={
                  streaming ||
                  researchBusy ||
                  !question.trim() ||
                  runtimeMode === 'mock'
                }
                onClick={() => void startResearch()}
              >
                {researchBusy
                  ? 'Starting research…'
                  : 'Research saved evidence in background'}
              </Button>
              {streaming && (
                <Button
                  type="button"
                  className="border border-slate-300 bg-white text-slate-700"
                  onClick={() => controller.current?.abort()}
                >
                  Stop
                </Button>
              )}
              <Button
                className={actionClass}
                disabled={streaming || !question.trim()}
                type="submit"
              >
                <Search className="size-4" />
                {streaming
                  ? 'Receiving answer…'
                  : mode === 'saved'
                    ? 'Search saved evidence'
                    : mode === 'auto'
                      ? 'Ask market'
                      : 'Ask DeepInsight AI'}
              </Button>
            </div>
          </div>
          {researchJobId && (
            <p role="status" className="text-xs text-teal-800">
              Research queued without a model call.{' '}
              <Link className="underline" href="/jobs">
                View Job Status ({researchJobId})
              </Link>
              . Findings remain subject to source and review gates.
            </p>
          )}
          {researchError && (
            <p role="alert" className="text-xs text-red-800">
              {researchError}
            </p>
          )}
        </form>
      </Panel>
      <p className="flex items-center gap-2 text-xs text-slate-500">
        <Clock3 className="size-3" />
        Conversation started in this browser view. Native chat provides durable
        session history.
      </p>
    </>
  )
}
