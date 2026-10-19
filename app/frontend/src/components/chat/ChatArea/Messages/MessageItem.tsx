import Icon from '@/components/ui/icon'
import MarkdownRenderer from '@/components/ui/typography/MarkdownRenderer'
import { useStore } from '@/store'
import type { ChatMessage } from '@/types/os'
import Videos from './Multimedia/Videos'
import Images from './Multimedia/Images'
import Audios from './Multimedia/Audios'
import { memo } from 'react'
import AgentThinkingLoader from './AgentThinkingLoader'
import {
  delimitEvidenceLinks,
  readEvidencePack,
  evidenceUrls
} from '@/lib/chat-evidence'
import { splitResearchInput } from '@/lib/workflow'
import { chatFailureCopy } from '@/lib/chat-errors'
import { publicationLabel } from '@/lib/publication'
import { englishDisplay } from '@/lib/english-output'
import SavedReport from '@/components/market/ReportArtifact'
import { reportIdFromTools } from '@/lib/report-artifact'

interface MessageProps {
  message: ChatMessage
}

const AgentMessage = ({ message }: MessageProps) => {
  const { streamingErrorMessage } = useStore()
  const reportId = reportIdFromTools(message.tool_calls)
  const urls = (message.tool_calls || []).flatMap((tool) =>
    evidenceUrls(readEvidencePack(tool.result ?? tool.content))
  )
  let messageContent
  if (message.streamingError) {
    messageContent = (
      <div className="text-destructive">
        <p>
          {chatFailureCopy(
            message.errorMessage ||
              streamingErrorMessage ||
              'FINAL_ANSWER_MISSING'
          )}
        </p>
        <details className="mt-2 text-xs">
          <summary>Technical details</summary>
          {englishDisplay(
            message.errorMessage ||
              streamingErrorMessage ||
              'FINAL_ANSWER_MISSING'
          )}
        </details>
      </div>
    )
  } else if (message.content) {
    messageContent = (
      <div className="flex w-full flex-col gap-4">
        <p className="text-xs text-muted">
          {message.operation
            ? `Saved-record operation: ${message.operation.replaceAll('_', ' ')} · no model call`
            : message.publicationOrigin
              ? publicationLabel(message.publicationOrigin)
              : 'AI interpretation · Check each source and reporting period. A completed response does not approve its evidence.'}
        </p>
        <MarkdownRenderer>
          {delimitEvidenceLinks(englishDisplay(message.content), urls)}
        </MarkdownRenderer>
        {message.videos && message.videos.length > 0 && (
          <Videos videos={message.videos} />
        )}
        {message.images && message.images.length > 0 && (
          <Images images={message.images} />
        )}
        {message.audio && message.audio.length > 0 && (
          <Audios audio={message.audio} />
        )}
      </div>
    )
  } else if (message.response_audio) {
    if (!message.response_audio.transcript) {
      messageContent = (
        <div className="mt-2 flex items-start">
          <AgentThinkingLoader />
        </div>
      )
    } else {
      messageContent = (
        <div className="flex w-full flex-col gap-4">
          <MarkdownRenderer>
            {message.response_audio.transcript}
          </MarkdownRenderer>
          {message.response_audio.content && message.response_audio && (
            <Audios audio={[message.response_audio]} />
          )}
        </div>
      )
    }
  } else {
    messageContent = (
      <div className="mt-2">
        <AgentThinkingLoader />
      </div>
    )
  }

  return (
    <div className="flex min-w-0 flex-row items-start gap-3 font-geist">
      <div className="flex-shrink-0">
        <Icon type="agent" size="sm" />
      </div>
      <div className="min-w-0 flex-1 space-y-4">
        {reportId && (
          <SavedReport
            key={`${reportId}:${message.content ? 'final' : 'pending'}:${message.streamingError ? 'failed' : ''}`}
            reportId={reportId}
          />
        )}
        {messageContent}
      </div>
    </div>
  )
}

const UserMessage = memo(({ message }: MessageProps) => {
  const input = splitResearchInput(message.content)
  return (
    <div className="chat-user">
      <div>{input.question}</div>
      {input.context && (
        <details className="mt-3 text-xs">
          <summary>Included saved evidence</summary>
          <pre className="mt-2 whitespace-pre-wrap break-words">
            {input.context}
          </pre>
        </details>
      )}
    </div>
  )
})

AgentMessage.displayName = 'AgentMessage'
UserMessage.displayName = 'UserMessage'
export { AgentMessage, UserMessage }
