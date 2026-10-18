export type EvidenceFact = {
  id: string
  metric?: string
  geography?: string
  value?: string | number
  unit?: string
  period?: string
  status?: string
  definition?: string
  document_id?: string
  evidence?: { quote?: string; page?: number; locator?: string }
}
export type EvidenceDocument = {
  title?: string
  publisher?: string
  published_at?: string
  url?: string
}
export type PublisherReportedChange = {
  id: string
  classification: 'publisher_reported_change'
  period?: string
  comparison_period?: string
  geography?: string
  definition?: string
  reported_value?: string | number
  reported_unit?: string
  reported_change?: string | number
  change_unit?: string
  calculation_performed?: boolean
  human_review_status?: string
  status?: string
  evidence?: { quote?: string; page?: number; locator?: string }
  document_id?: string
  document_sha256?: string
  report_title?: string
  published_at?: string
  url?: string
  limitation?: string
}
export function readEvidencePack(raw: unknown): {
  facts: EvidenceFact[]
  publisherReportedChanges: PublisherReportedChange[]
  documents: Record<string, EvidenceDocument>
  notice?: string
} | null {
  try {
    const data = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (
      !data ||
      typeof data !== 'object' ||
      (!Array.isArray(data.facts) &&
        !Array.isArray(data.publisher_reported_changes))
    )
      return null
    return {
      facts: (Array.isArray(data.facts) ? data.facts : []).filter(
        (f: EvidenceFact) => f && typeof f.id === 'string'
      ),
      publisherReportedChanges: (Array.isArray(data.publisher_reported_changes)
        ? data.publisher_reported_changes
        : []
      ).filter(
        (item: PublisherReportedChange) =>
          item &&
          typeof item.id === 'string' &&
          item.classification === 'publisher_reported_change'
      ),
      documents:
        data.documents && typeof data.documents === 'object'
          ? data.documents
          : {},
      notice:
        typeof data.review_notice === 'string' ? data.review_notice : undefined
    }
  } catch {
    return null
  }
}
export function evidenceUrls(pack: ReturnType<typeof readEvidencePack>) {
  if (!pack) return []
  return [
    ...Object.values(pack.documents).map((doc) => doc.url || ''),
    ...pack.publisherReportedChanges.map((change) => change.url || '')
  ].filter((url) => Boolean(safeEvidenceUrl(url)))
}
export function safeEvidenceUrl(url?: string) {
  if (!url) return undefined
  try {
    const parsed = new URL(url)
    return ['http:', 'https:'].includes(parsed.protocol)
      ? parsed.href
      : undefined
  } catch {
    return undefined
  }
}
export function reviewLabel(status?: string) {
  return (
    (
      {
        approved: 'Approved',
        pending_review: 'Pending review · 待核实',
        needs_review: 'Needs review · 待核实',
        rejected: 'Rejected'
      } as Record<string, string>
    )[status || ''] || 'Unknown review status'
  )
}

// Only delimit URLs supplied by the actual tool result. Never invent or repair an unknown source.
export function delimitEvidenceLinks(text: string, urls: string[]) {
  let result = text
  for (const url of new Set(urls.filter((url) => safeEvidenceUrl(url)))) {
    const escaped = url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    result = result.replace(
      new RegExp(`${escaped}(?=[，。；、（）])`, 'g'),
      `<${url}>`
    )
  }
  return result
}
