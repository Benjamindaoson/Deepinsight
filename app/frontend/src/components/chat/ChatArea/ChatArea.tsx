'use client'

import ChatInput from './ChatInput'
import MessageArea from './MessageArea'
import { useStore } from '@/store'
import { useQueryState } from 'nuqs'
const ChatArea = () => {
  const empty = useStore((s) => s.messages.length === 0)
  const restoring = useStore((s) => s.sessionLoad.status === 'loading')
  const historyError = useStore((s) => s.sessionLoad.status === 'error')
  const [session] = useQueryState('session')
  return (
    <main className={`chat-page ${empty ? 'chat-empty' : ''}`}>
      {session && (restoring || historyError) ? (
        <p role="status" className="p-6">
          {restoring
            ? 'Restoring your conversation…'
            : 'This conversation is not loaded. Use Reload this conversation below.'}
        </p>
      ) : empty ? (
        <div className="chat-welcome">
          <div className="welcome-mark" aria-hidden="true">
            L
          </div>
          <h1>London Office Intelligence</h1>
          <p>Research, monitor and understand the London office market.</p>
        </div>
      ) : (
        <MessageArea />
      )}
      <ChatInput welcome={empty} />
    </main>
  )
}

export default ChatArea
