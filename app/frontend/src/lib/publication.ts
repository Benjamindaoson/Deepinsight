/** Read-only publication view. Never submits or retries a native Run. */
export interface Publication {
  report_id?: string
  answer: string
  answer_origin: 'deterministic_evidence_fallback' | 'ai_limited_checks'
  publication_review: {
    status: 'withheld' | 'limited_checks_passed'
    semantic_approval: false
    codes: string[]
  }
}

export const publicationLabel = (origin?: string) =>
  origin === 'deterministic_evidence_fallback'
    ? 'Model conclusions withheld · verified source records shown · human review required'
    : 'Model findings passed limited automated checks · human review still required'

export async function getPublication(
  endpoint: string,
  session: string,
  run: string,
  token?: string
): Promise<Publication> {
  const response = await fetch(
    `${endpoint.replace(/\/$/, '')}/api/market/sessions/${encodeURIComponent(session)}/runs/${encodeURIComponent(run)}/publication`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: 'no-store'
    }
  )
  if (!response.ok)
    throw new Error(
      `Publication check did not complete (${response.status}). The raw draft remains hidden. No model retry was made; inspect Job Status before retrying.`
    )
  const result = await response.json()
  if (
    !result.answer ||
    !['deterministic_evidence_fallback', 'ai_limited_checks'].includes(
      result.answer_origin
    )
  )
    throw new Error(
      'The publication result is incomplete. The raw draft remains hidden. No model retry was made; inspect Job Status.'
    )
  return result
}
