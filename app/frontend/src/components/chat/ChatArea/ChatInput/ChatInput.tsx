'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ArrowUp, Square, ArrowUpRight } from 'lucide-react'
import { useStore } from '@/store'
import useAIChatStreamHandler from '@/hooks/useAIStreamHandler'
import { useQueryState } from 'nuqs'
import useSessionLoader from '@/hooks/useSessionLoader'
import ResearchContext from '@/components/chat/ResearchContext'
import { chatFailureCopy } from '@/lib/chat-errors'
import {
  attachResearchContext,
  splitResearchInput,
  contextIsReady,
  latestChatFailure
} from '@/lib/workflow'

const prompts = [
  'What changed in the London office market this quarter?',
  'Compare prime rents across City and West End.',
  'What are the latest major leasing and supply events?',
  'What risks and opportunities should occupiers watch?'
]
const ChatInput = ({ welcome = false }: { welcome?: boolean }) => {
  const { chatInputRef } = useStore()
  const { handleStreamResponse, stopResponse } = useAIChatStreamHandler()
  const [agent] = useQueryState('agent')
  const [team] = useQueryState('team')
  const [session] = useQueryState('session')
  const [dbId] = useQueryState('db_id')
  const { getSession } = useSessionLoader()
  const [input, setInput] = useState('')
  const [selectedEvidence, setSelectedEvidence] = useState('')
  const [contextKind] = useQueryState('context')
  const [contextRecord] = useQueryState('record')
  const [contextReady, setContextReady] = useState<string | null>(null)
  const ready = contextIsReady(contextKind, contextRecord, contextReady)
  const contextBlocked = Boolean(contextKind && !ready)
  const revision = useStore((s) => s.composerRevision)
  const previousRevision = useRef(revision)
  useEffect(() => {
    if (previousRevision.current === revision) return
    previousRevision.current = revision
    setInput('')
    setSelectedEvidence('')
  }, [revision])
  const streaming = useStore((s) => s.isStreaming)
  const active = useStore((s) => s.isEndpointActive)
  const error = useStore(
    (s) => s.streamingErrorMessage || latestChatFailure(s.messages)
  )
  const history = useStore((s) => s.sessionLoad)
  const historyBlocked = Boolean(
    session &&
      history.id === session &&
      ['loading', 'error'].includes(history.status)
  )
  const lastQuestion = useStore(
    (s) => s.messages.findLast((m) => m.role === 'user')?.content
  )
  const pending = useRef(false)
  const applyDraft = useCallback(
    (draft: string, evidence = '') => {
      setInput(draft)
      setSelectedEvidence(evidence)
      if (draft) {
        useStore.getState().setMessages([])
        useStore.getState().setStreamingErrorMessage('')
        useStore
          .getState()
          .setSessionLoad({ id: null, status: 'idle', error: '' })
      }
      chatInputRef.current?.focus()
    },
    [chatInputRef]
  )
  const submit = async (text = input) => {
    if (
      !text.trim() ||
      pending.current ||
      streaming ||
      historyBlocked ||
      contextBlocked ||
      !active ||
      !(agent || team)
    )
      return
    pending.current = true
    setInput('')
    try {
      await handleStreamResponse(
        attachResearchContext(text, ready ? selectedEvidence : '')
      )
    } finally {
      pending.current = false
    }
  }
  return (
    <div className="composer-area">
      <ResearchContext
        onDraft={applyDraft}
        onReady={setContextReady}
        streaming={streaming}
      />
      <form
        className="chat-composer"
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <textarea
          aria-label="Message DeepInsight AI"
          placeholder="Ask DeepInsight AI about the London office market…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={2}
          ref={chatInputRef}
          onKeyDown={(e) => {
            if (
              e.key === 'Enter' &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault()
              void submit()
            }
          }}
        />
        <div className="composer-bottom">
          <span>
            DeepInsight AI{' '}
            <details className="sources-tools">
              <summary>Sources & capabilities</summary>
              <p>
                Answers use saved market evidence and may call the configured
                model. Current source availability does not mean an observation
                has been verified. This quarter means the period you specify;
                latest saved data may be older.
              </p>
              <div>
                <Link href="/market-data">Inspect source data</Link> ·{' '}
                <Link href="/ask">Search saved records without AI</Link> ·{' '}
                <Link href="/reports">Create a briefing</Link> ·{' '}
                <Link href="/settings">Configure monitoring</Link>
              </div>
              <p>
                Reports and monitoring are configured on their pages; a chat
                response alone does not create or change them.
              </p>
            </details>
          </span>
          {streaming ? (
            <button
              type="button"
              className="send-button"
              aria-label="Stop generating"
              onClick={stopResponse}
            >
              <Square size={16} fill="currentColor" />
            </button>
          ) : (
            <button
              className="send-button"
              type="submit"
              aria-label="Send message"
              disabled={
                !input.trim() ||
                !active ||
                !(agent || team) ||
                historyBlocked ||
                contextBlocked
              }
            >
              <ArrowUp size={20} />
            </button>
          )}
        </div>
      </form>
      {history.id === session && history.status === 'error' && (
        <div className="chat-error" role="alert">
          <p>
            This conversation could not be restored. Your saved conversation has
            not been deleted. No question was sent.
          </p>
          <button
            onClick={() =>
              session &&
              void getSession(
                {
                  entityType: agent ? 'agent' : 'team',
                  agentId: agent,
                  teamId: team,
                  dbId
                },
                session
              )
            }
          >
            Reload this conversation
          </button>
          <details>
            <summary>Technical details</summary>
            {history.error}
          </details>
        </div>
      )}
      {streaming && (
        <p role="status" className="composer-note">
          Working with saved evidence… You can stop generation.
        </p>
      )}
      {!active && (
        <p role="status" className="composer-note">
          Connecting to DeepInsight AI. Check Connection settings if this
          persists.
        </p>
      )}
      {error && !streaming && !historyBlocked && (
        <div className="chat-error" role="alert">
          <p>{chatFailureCopy(error)}</p>
          <details>
            <summary>Technical details</summary>
            {error}
          </details>
          <button
            onClick={() => {
              setInput(splitResearchInput(lastQuestion || '').question)
              chatInputRef.current?.focus()
            }}
          >
            Edit question to retry
          </button>
        </div>
      )}
      {welcome && (
        <div className="quick-prompts">
          {prompts.map((prompt, i) => (
            <button
              key={prompt}
              disabled={!active || !(agent || team) || streaming}
              onClick={() => {
                setInput(prompt)
                chatInputRef.current?.focus()
              }}
            >
              <span className="prompt-topic">
                {
                  [
                    'Market changes',
                    'Compare markets',
                    'Leasing & supply',
                    'Risks & opportunities'
                  ][i]
                }
              </span>
              <span>{prompt}</span>
              <ArrowUpRight size={15} />
            </button>
          ))}
        </div>
      )}
      <p className="composer-note">
        Source-reported observations may be unreviewed. AI interpretation is not
        verified market data. Suggested questions fill the input; send when
        ready.
      </p>
    </div>
  )
}
export default ChatInput
