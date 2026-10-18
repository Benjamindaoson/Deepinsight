export function chatFailureCopy(raw: string) {
  if (/PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED/.test(raw))
    return 'The provider reported usage above a configured limit. Further requests were stopped; any draft is unaccepted. No automatic retry.'
  if (/PROVIDER_USAGE_MISSING/.test(raw))
    return 'The provider usage receipt is missing. Further requests were stopped because the remaining budget cannot be confirmed.'
  if (/STOP_REQUESTED|AbortError/.test(raw))
    return 'Generation was stopped. Any partial draft remains incomplete. Review it before sending another question.'
  if (/TOKEN_BUDGET|context.*limit/i.test(raw))
    return 'The context or token budget prevented completion. Narrow the question or start a new conversation; there is no automatic retry.'
  if (/timeout|timed.out/i.test(raw))
    return 'The research time limit was reached. A final answer is not confirmed. You can edit the question before retrying.'
  if (/401|403|API.?key|unauthori|credential|configuration/i.test(raw))
    return 'The AI service configuration needs attention. Check Connection settings or ask the service administrator to review server credentials.'
  if (/no.usable.sources|no.sources/i.test(raw))
    return 'No usable sources were returned. Inspect saved market data or try a different geography or reporting period.'
  if (/503|unavailable/i.test(raw))
    return 'The research service is temporarily unavailable. Check service availability before retrying.'
  if (/fetch|network|connect/i.test(raw))
    return 'The connection to the research service failed. Check the connection; your submitted question can be edited and retried.'
  return 'Research did not produce a confirmed final answer. Any partial draft requires review. Edit the question to try again.'
}

export function explainChatError(raw: string) {
  if (/PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED/.test(raw))
    return 'PROVIDER_REPORTED_TOKEN_LIMIT_EXCEEDED: Provider reported usage exceeded a configured limit. Retrieval or a draft may exist, but final analysis was not accepted. Further requests stopped. No automatic retry; already incurred usage cannot be undone.'
  if (/PROVIDER_USAGE_MISSING/.test(raw))
    return 'PROVIDER_USAGE_MISSING: A reliable usage receipt was not returned. Remaining budget is unknown, so continuation stopped. No final analysis is confirmed and there is no automatic retry.'
  if (/AbortError/.test(raw))
    return 'STOP_REQUESTED: Streaming was stopped. Any partial draft remains incomplete; the provider may already have used tokens.'
  if (/TOKEN_BUDGET/.test(raw))
    return `TOKEN_BUDGET_EXCEEDED: The existing context or token budget blocked continuation. Retrieval may have completed, but no final analysis is confirmed. No automatic retry. Details: ${raw}`
  if (/timeout|timed out/i.test(raw))
    return `MODEL_TIMEOUT: The model did not finish within the configured time. The draft is incomplete. No automatic retry. Details: ${raw}`
  if (/FINAL_ANSWER_MISSING/.test(raw))
    return 'FINAL_ANSWER_MISSING: The run ended without a complete final answer; its draft remains incomplete. Tool results are evidence only, not a completed analysis.'
  return `The Agent run did not complete successfully. Any displayed draft requires review. No automatic retry. Details: ${raw}`
}

export function restoredRunError(run: {
  status?: string
  events?: Array<{ event?: string; content?: unknown }>
}) {
  const error = run.events?.find((event) =>
    /^(Team)?RunError$/.test(event.event || '')
  )
  if (error)
    return explainChatError(String(error.content || 'FINAL_ANSWER_MISSING'))
  if (run.status && run.status.toUpperCase() !== 'COMPLETED')
    return explainChatError('FINAL_ANSWER_MISSING')
  return ''
}
