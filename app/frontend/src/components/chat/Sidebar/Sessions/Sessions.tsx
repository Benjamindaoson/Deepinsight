'use client'

import { FC, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryState } from 'nuqs'
import { usePathname } from 'next/navigation'

import { useStore } from '@/store'
import useSessionLoader from '@/hooks/useSessionLoader'

import SessionItem from './SessionItem'
import SessionBlankState from './SessionBlankState'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface SkeletonListProps {
  skeletonCount: number
}
const SkeletonList: FC<SkeletonListProps> = ({ skeletonCount }) => {
  const list = useMemo(
    () => Array.from({ length: skeletonCount }, (_, i) => i),
    [skeletonCount]
  )

  return list.map((k, idx) => (
    <Skeleton
      key={k}
      className={cn(
        'mb-1 h-11 rounded-lg px-3 py-2',
        idx > 0 && 'bg-background-secondary'
      )}
    />
  ))
}

const Sessions = ({ search = '' }: { search?: string }) => {
  const pathname = usePathname()
  const streaming = useStore((s) => s.isStreaming)
  const [agentId] = useQueryState('agent', {
    parse: (v: string | null) => v || undefined,
    history: 'push'
  })
  const [teamId] = useQueryState('team')
  const [sessionId] = useQueryState('session')
  const [dbId] = useQueryState('db_id')

  const {
    selectedEndpoint,
    mode,
    isEndpointActive,
    isEndpointLoading,
    hydrated,
    sessionsData,
    setSessionsData,
    isSessionsLoading,
    historyError
  } = useStore()

  const [isScrolling, setIsScrolling] = useState(false)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null
  )

  const { getSessions, getSession } = useSessionLoader()
  const scrollTimeoutRef = useRef<ReturnType<typeof setTimeout>>(null)

  const handleScroll = () => {
    setIsScrolling(true)

    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current)
    }

    scrollTimeoutRef.current = setTimeout(() => {
      setIsScrolling(false)
    }, 1500)
  }

  // Cleanup the scroll timeout when component unmounts
  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (
      hydrated &&
      sessionId &&
      selectedEndpoint &&
      (agentId || teamId) &&
      !useStore.getState().isStreaming &&
      (pathname === '/' || pathname === '/chat')
    ) {
      const entityType = agentId ? 'agent' : 'team'
      getSession({ entityType, agentId, teamId, dbId }, sessionId)
    }
  }, [
    hydrated,
    sessionId,
    selectedEndpoint,
    agentId,
    teamId,
    dbId,
    pathname,
    getSession
  ])

  useEffect(() => {
    if (!selectedEndpoint || isEndpointLoading) return
    if (!(agentId || teamId || dbId)) {
      setSessionsData([])
      return
    }
    setSessionsData([])
    getSessions({
      entityType: mode,
      agentId,
      teamId,
      dbId
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    selectedEndpoint,
    agentId,
    teamId,
    mode,
    isEndpointLoading,
    getSessions,
    dbId
  ])

  useEffect(() => {
    setSelectedSessionId(sessionId)
  }, [sessionId])

  const handleSessionClick = useCallback(
    (id: string) => () => setSelectedSessionId(id),
    []
  )

  if (isSessionsLoading || isEndpointLoading) {
    return (
      <div className="w-full">
        <div className="mb-2 text-xs font-medium uppercase">
          Loading conversations
        </div>
        <div className="mt-2 w-full overflow-y-auto">
          <SkeletonList skeletonCount={5} />
        </div>
      </div>
    )
  }

  return (
    <div className="w-full">
      <div className="nav-label">Recent conversations</div>
      {historyError && (
        <div role="alert" className="p-2 text-xs">
          <p>Conversations could not be loaded.</p>
          <button
            className="underline"
            onClick={() =>
              void getSessions({ entityType: mode, agentId, teamId, dbId })
            }
          >
            Reload conversations
          </button>
          <details>
            <summary>Technical details</summary>
            {historyError}
          </details>
        </div>
      )}
      <div
        className={`session-list overflow-y-auto font-geist ${streaming ? 'pointer-events-none opacity-60' : ''} ${
          isScrolling
            ? '[&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-background [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar]:opacity-0'
            : '[&::-webkit-scrollbar]:opacity-100'
        }`}
        onScroll={handleScroll}
        onMouseOver={() => setIsScrolling(true)}
        onMouseLeave={handleScroll}
      >
        {!isEndpointActive ||
        (!historyError &&
          !isSessionsLoading &&
          (!sessionsData || sessionsData?.length === 0)) ? (
          <SessionBlankState />
        ) : (
          <div className="flex flex-col gap-y-1 pr-1">
            {sessionsData
              ?.filter((entry) =>
                entry.session_name?.toLowerCase().includes(search.toLowerCase())
              )
              .map((entry, idx) => (
                <SessionItem
                  key={`${entry?.session_id}-${idx}`}
                  currentSessionId={selectedSessionId}
                  isSelected={selectedSessionId === entry?.session_id}
                  onSessionClick={handleSessionClick(entry?.session_id)}
                  session_name={entry?.session_name ?? '-'}
                  session_id={entry?.session_id}
                  created_at={entry?.created_at}
                />
              ))}
          </div>
        )}
        {search &&
          !sessionsData?.some((entry) =>
            entry.session_name?.toLowerCase().includes(search.toLowerCase())
          ) && <p className="p-3 text-xs text-muted">No matching chats.</p>}
      </div>
    </div>
  )
}

export default Sessions
