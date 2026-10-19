import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useStore } from '@/store'
import { constructEndpointUrl } from '@/lib/constructEndpointUrl'

export type Connection = {
  id: string
  name: string
  base_url: string
  key_hint: string
  models: string[]
  status: string
}
export type Attachment = {
  id: string
  name: string
  sha256: string
  media: string
  bytes: number
  segment_count: number
  review_status: string
}
export const usePersonalModels = create<{
  open: boolean
  setOpen: (open: boolean) => void
  connections: Connection[]
  setConnections: (connections: Connection[]) => void
  connectionId: string
  model: string
  thinking: 'standard' | 'deep'
  select: (connectionId: string, model: string) => void
  setThinking: (thinking: 'standard' | 'deep') => void
  attachments: Attachment[]
  setAttachments: (attachments: Attachment[]) => void
  progress: string
  setProgress: (progress: string) => void
}>()(
  persist(
    (set) => ({
      open: false,
      setOpen: (open) => set({ open }),
      connections: [],
      setConnections: (connections) => set({ connections }),
      connectionId: '',
      model: '',
      thinking: 'standard',
      select: (connectionId, model) =>
        set({ connectionId, model, thinking: 'standard' }),
      setThinking: (thinking) => set({ thinking }),
      attachments: [],
      progress: '',
      setProgress: (progress) => set({ progress }),
      setAttachments: (attachments) => set({ attachments })
    }),
    {
      name: 'deepinsight-personal-model-choice',
      partialize: (state) => ({
        connectionId: state.connectionId,
        model: state.model,
        thinking: state.thinking
      })
    }
  )
)

export function personalUrl(path: string) {
  return `${constructEndpointUrl(useStore.getState().selectedEndpoint)}/api/market${path}`
}
export async function personalApi<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = useStore.getState().authToken
  const response = await fetch(personalUrl(path), {
    ...options,
    credentials: 'include',
    headers: {
      ...(options.body && !(options.body instanceof FormData)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  })
  const result = await response.json()
  if (!response.ok)
    throw new Error(
      typeof result.detail === 'string'
        ? result.detail
        : `Request failed (${response.status})`
    )
  return result as T
}
export function supportsThinking(connection?: Connection, model = '') {
  return (
    /^https:\/\/api\.deepseek\.com(?:\/v1)?\/?$/.test(
      connection?.base_url || ''
    ) &&
    [
      'deepseek-flash',
      'deepseek-v4-pro',
      'deepseek-chat',
      'deepseek-reasoner'
    ].includes(model)
  )
}

export function chatModelCandidate(model: string) {
  return (
    /^(gpt-|claude-|gemini-|deepseek-|qwen|kimi|glm-|grok-)/i.test(model) &&
    !/image|embedding|tts|whisper|dall-e|video|sora|audio|realtime|codex|nano.banana|omni/i.test(
      model
    )
  )
}
