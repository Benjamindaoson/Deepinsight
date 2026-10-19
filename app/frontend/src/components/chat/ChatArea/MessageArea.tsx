'use client'

import { useStore } from '@/store'
import Messages from './Messages'
import ScrollToBottom from '@/components/chat/ChatArea/ScrollToBottom'
import { StickToBottom } from 'use-stick-to-bottom'

const MessageArea = () => {
  const { messages } = useStore()

  return (
    <StickToBottom
      className="relative min-h-0 flex-grow overflow-hidden"
      resize="smooth"
      initial="smooth"
    >
      <StickToBottom.Content className="flex min-h-full flex-col">
        <div className="chat-messages mx-auto w-full max-w-[800px] space-y-7 px-5 has-[[data-report-id]]:max-w-[1160px]">
          <Messages messages={messages} />
        </div>
      </StickToBottom.Content>
      <ScrollToBottom />
    </StickToBottom>
  )
}

export default MessageArea
