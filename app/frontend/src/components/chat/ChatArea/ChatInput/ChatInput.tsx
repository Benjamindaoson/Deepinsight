'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import {
  ArrowUp,
  Square,
  ArrowUpRight,
  Plus,
  X,
  SlidersHorizontal,
  FileText
} from 'lucide-react'
import {
  personalApi,
  personalUrl,
  chatModelCandidate,
  supportsThinking,
  usePersonalModels,
  type Attachment
} from '@/lib/personal-models'
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
  const personal = usePersonalModels()
  const fileInput = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const connection = personal.connections.find(
    (c) => c.id === personal.connectionId
  )
  async function upload(files: FileList | null) {
    if (!files?.length) return
    setUploading(true)
    setUploadError('')
    try {
      await personalApi('/model-connections')
      for (const file of Array.from(files)) {
        if (usePersonalModels.getState().attachments.length >= 4)
          throw new Error('Attach at most four files per message.')
        const body = new FormData()
        body.append('file', file)
        const saved = await personalApi<Attachment>('/attachments', {
          method: 'POST',
          body
        })
        personal.setAttachments([
          ...usePersonalModels.getState().attachments,
          saved
        ])
      }
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed.')
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }
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
    usePersonalModels.getState().setAttachments([])
    setUploadError('')
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
      uploading ||
      pending.current ||
      streaming ||
      historyBlocked ||
      contextBlocked ||
      !active ||
      !(agent || team)
    )
      return
    pending.current = true
    if (personal.attachments.length && !personal.connectionId) {
      personal.setOpen(true)
      pending.current = false
      return
    }
    setInput('')
    try {
      await handleStreamResponse(
        attachResearchContext(text, ready ? selectedEvidence : '')
      )
      if (useStore.getState().streamingErrorMessage) setInput(text)
      else personal.setAttachments([])
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
        <input
          ref={fileInput}
          type="file"
          className="sr-only"
          accept=".pdf,.txt,.md,.csv"
          multiple
          aria-label="Upload reference files"
          onChange={(e) => void upload(e.target.files)}
        />
        {personal.attachments.length > 0 && (
          <div className="attachment-chips">
            {personal.attachments.map((file) => (
              <div key={file.id}>
                <FileText size={18} />
                <a
                  href={personalUrl(`/attachments/${file.id}`)}
                  target="_blank"
                  rel="noreferrer"
                >
                  {file.name}
                </a>
                <span title="Original retained. Only bounded text excerpts are sent to the selected model; uploads do not approve market facts.">
                  {file.segment_count} sections · unreviewed excerpts
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${file.name}`}
                  onClick={() =>
                    personal.setAttachments(
                      personal.attachments.filter((f) => f.id !== file.id)
                    )
                  }
                >
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
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
          <div className="composer-actions">
            <button
              type="button"
              className="attach-button"
              aria-label="Add files"
              title="Upload PDF, TXT, Markdown or CSV"
              disabled={uploading || streaming}
              onClick={() => fileInput.current?.click()}
            >
              <Plus size={25} />
            </button>
            <span className="composer-source-link">
              <details className="sources-tools">
                <summary>Sources & capabilities</summary>
                <p>
                  Answers use saved market evidence and may call the configured
                  model. Current source availability does not mean an
                  observation has been verified. This quarter means the period
                  you specify; latest saved data may be older.
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
          </div>
          <div className="composer-model-controls">
            <label className="sr-only" htmlFor="chat-model-select">
              Chat model
            </label>
            <select
              id="chat-model-select"
              aria-label="Chat model"
              disabled={streaming}
              value={
                personal.connectionId
                  ? `${personal.connectionId}|${personal.model}`
                  : 'system'
              }
              onChange={(e) => {
                if (e.target.value === 'manage') personal.setOpen(true)
                else if (e.target.value === 'system') personal.select('', '')
                else {
                  const [id, model] = e.target.value.split('|')
                  personal.select(id, model)
                }
              }}
            >
              <option value="system">Shared service</option>
              {personal.connections.map((c) => (
                <optgroup label={c.name} key={c.id}>
                  {c.models.filter(chatModelCandidate).map((m) => (
                    <option key={m} value={`${c.id}|${m}`}>
                      {m}
                    </option>
                  ))}
                </optgroup>
              ))}
              <option value="manage">Manage models & API keys…</option>
            </select>
            <select
              aria-label="Thinking mode"
              disabled={
                streaming || !supportsThinking(connection, personal.model)
              }
              value={personal.thinking}
              title={
                supportsThinking(connection, personal.model)
                  ? 'Choose the provider thinking mode'
                  : 'Thinking controls are not verified for this connection/model'
              }
              onChange={(e) =>
                personal.setThinking(e.target.value as 'standard' | 'deep')
              }
            >
              <option value="standard">Standard</option>
              <option value="deep">Deep thinking</option>
            </select>
            <button
              type="button"
              className="composer-settings"
              aria-label="Model settings"
              onClick={() => personal.setOpen(true)}
            >
              <SlidersHorizontal size={20} />
            </button>
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
                  uploading ||
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
        </div>
      </form>
      {uploading && (
        <p role="status" className="composer-note">
          Uploading and parsing your document…
        </p>
      )}
      {uploadError && (
        <p role="alert" className="chat-error">
          {uploadError}
        </p>
      )}
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
          {personal.progress ||
            'Working with saved evidence… You can stop generation.'}
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
          <button onClick={() => personal.setOpen(true)}>
            Change model or API key
          </button>
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
