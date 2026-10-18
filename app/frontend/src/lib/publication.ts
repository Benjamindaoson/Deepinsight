/** Read-only publication view. Never submits or retries a native Run. */
export interface Publication {
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
    ? 'AI 草稿已拦截 · 现展示基于证据的安全回答 · 未新增模型调用 · REVIEW_REQUIRED'
    : 'AI 分析通过有限自动检查 · 不代表语义或人工审核通过 · REVIEW_REQUIRED'

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
      `发布检查未完成 (${response.status})。原始草稿未展示；没有重新调用模型。`
    )
  const result = await response.json()
  if (
    !result.answer ||
    !['deterministic_evidence_fallback', 'ai_limited_checks'].includes(
      result.answer_origin
    )
  )
    throw new Error('发布结果不完整。原始草稿未展示；没有重新调用模型。')
  return result
}
