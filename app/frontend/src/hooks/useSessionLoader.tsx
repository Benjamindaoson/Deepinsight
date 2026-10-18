import { useCallback } from 'react'
import { getSessionAPI, getAllSessionsAPI } from '@/api/os'
import { useStore } from '../store'
import { ChatMessage, ToolCall, ReasoningMessage, ChatEntry } from '@/types/os'
import { getJsonMarkdown } from '@/lib/utils'
import { createSelectionGuard } from '@/lib/workflow'
import { restoredRunError } from '@/lib/chat-errors'
import { getPublication, type Publication } from '@/lib/publication'
import { constructEndpointUrl } from '@/lib/constructEndpointUrl'

const selectionGuard = createSelectionGuard()
let listSequence = 0

interface SessionResponse {
  session_id: string
  agent_id: string
  user_id: string | null
  runs?: ChatEntry[]
  memory: {
    runs?: ChatEntry[]
    chats?: ChatEntry[]
  }
  agent_data: Record<string, unknown>
}

interface LoaderArgs {
  entityType: 'agent' | 'team' | null
  agentId?: string | null
  teamId?: string | null
  dbId: string | null
}

const useSessionLoader = () => {
  const setMessages = useStore((state) => state.setMessages)
  const selectedEndpoint = useStore((state) => state.selectedEndpoint)
  const authToken = useStore((state) => state.authToken)
  const setIsSessionsLoading = useStore((state) => state.setIsSessionsLoading)
  const setSessionsData = useStore((state) => state.setSessionsData)

  const getSessions = useCallback(
    async ({ entityType, agentId, teamId, dbId }: LoaderArgs) => {
      const selectedId = entityType === 'agent' ? agentId : teamId
      if (!selectedEndpoint || !entityType || !selectedId || !dbId) return
      const sequence = ++listSequence
      try {
        setIsSessionsLoading(true)
        useStore.getState().setHistoryError('')

        const sessions = await getAllSessionsAPI(
          selectedEndpoint,
          entityType,
          selectedId,
          dbId,
          authToken
        )
        if (sequence === listSequence) setSessionsData(sessions.data ?? [])
      } catch (error) {
        if (sequence === listSequence)
          useStore
            .getState()
            .setHistoryError(
              error instanceof Error
                ? error.message
                : 'Could not load conversations.'
            )
      } finally {
        if (sequence === listSequence) setIsSessionsLoading(false)
      }
    },
    [selectedEndpoint, authToken, setSessionsData, setIsSessionsLoading]
  )

  const getSession = useCallback(
    async (
      { entityType, agentId, teamId, dbId }: LoaderArgs,
      sessionId: string
    ) => {
      const selectedId = entityType === 'agent' ? agentId : teamId
      if (
        !selectedEndpoint ||
        !sessionId ||
        !entityType ||
        !selectedId ||
        !dbId
      )
        return

      const ticket = selectionGuard.begin(sessionId)
      const current = () =>
        selectionGuard.current(
          ticket,
          new URL(window.location.href).searchParams.get('session'),
          useStore.getState().isStreaming
        ) &&
        selectedEndpoint === useStore.getState().selectedEndpoint &&
        authToken === useStore.getState().authToken
      if (!current()) return null
      useStore.getState().setStreamingErrorMessage('')
      useStore
        .getState()
        .setSessionLoad({ id: sessionId, status: 'loading', error: '' })
      try {
        const response: SessionResponse = await getSessionAPI(
          selectedEndpoint,
          entityType,
          sessionId,
          dbId,
          authToken
        )
        if (response) {
          if (Array.isArray(response)) {
            const publications = new Map<string, Publication>()
            if (entityType === 'agent' && agentId === 'london-market-agent') {
              // Read-only projection; no rewriting history or paid resubmission.
              for (const run of response) {
                if (!restoredRunError(run)) {
                  publications.set(
                    run.run_id,
                    await getPublication(
                      constructEndpointUrl(selectedEndpoint),
                      sessionId,
                      run.run_id,
                      authToken
                    )
                  )
                }
              }
            }
            const messagesFor = response.flatMap((run) => {
              const filteredMessages: ChatMessage[] = []

              if (run) {
                filteredMessages.push({
                  role: 'user',
                  content: run.run_input ?? '',
                  created_at: run.created_at
                })
              }

              if (run) {
                const toolCalls = [
                  ...(run.tools ?? []),
                  ...(run.extra_data?.reasoning_messages ?? []).reduce(
                    (acc: ToolCall[], msg: ReasoningMessage) => {
                      if (msg.role === 'tool') {
                        acc.push({
                          role: msg.role,
                          content: msg.content,
                          tool_call_id: msg.tool_call_id ?? '',
                          tool_name: msg.tool_name ?? '',
                          tool_args: msg.tool_args ?? {},
                          tool_call_error: msg.tool_call_error ?? false,
                          metrics: msg.metrics ?? { time: 0 },
                          created_at:
                            msg.created_at ?? Math.floor(Date.now() / 1000)
                        })
                      }
                      return acc
                    },
                    []
                  )
                ]

                filteredMessages.push({
                  role: 'agent',
                  content:
                    publications.get(run.run_id)?.answer ??
                    (restoredRunError(run)
                      ? ''
                      : ((run.content as string) ?? '')),
                  publicationOrigin: publications.get(run.run_id)
                    ?.answer_origin,
                  streamingError: Boolean(restoredRunError(run)),
                  errorMessage: restoredRunError(run),
                  tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
                  extra_data: publications.has(run.run_id)
                    ? undefined
                    : run.extra_data,
                  images: run.images,
                  videos: run.videos,
                  audio: run.audio,
                  response_audio: run.response_audio,
                  created_at: run.created_at
                })
              }
              return filteredMessages
            })

            const processedMessages = messagesFor.map(
              (message: ChatMessage) => {
                if (Array.isArray(message.content)) {
                  const textContent = message.content
                    .filter((item: { type: string }) => item.type === 'text')
                    .map((item) => item.text)
                    .join(' ')

                  return {
                    ...message,
                    content: textContent
                  }
                }
                if (typeof message.content !== 'string') {
                  return {
                    ...message,
                    content: getJsonMarkdown(message.content)
                  }
                }
                return message
              }
            )

            // A slow history response must never replace a newer chat or live run.
            if (!current()) return null
            setMessages(processedMessages)
            useStore
              .getState()
              .setSessionLoad({ id: sessionId, status: 'ready', error: '' })
            return processedMessages
          }
        }
        throw new Error(
          'The conversation service returned an unsupported response.'
        )
      } catch (error) {
        if (current())
          useStore.getState().setSessionLoad({
            id: sessionId,
            status: 'error',
            error: error instanceof Error ? error.message : String(error)
          })
        return null
      }
    },
    [selectedEndpoint, authToken, setMessages]
  )

  return { getSession, getSessions }
}

export default useSessionLoader
