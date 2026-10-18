'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { ThemeProvider, useTheme } from 'next-themes'
import {
  Building2,
  MessageSquare,
  LayoutDashboard,
  Database,
  Activity,
  FileText,
  Settings2,
  ClipboardList,
  PanelLeft,
  SquarePen,
  Search,
  Sun,
  Moon,
  X
} from 'lucide-react'
import { useStore } from '@/store'
import useChatActions from '@/hooks/useChatActions'
import Sessions from '@/components/chat/Sidebar/Sessions'
import AuthToken from '@/components/chat/Sidebar/AuthToken'
import { Toaster } from '@/components/ui/sonner'

const navigation = [
  ['/', 'DeepInsight AI', MessageSquare, 'AI Workspace'],
  ['/overview', 'Market Overview', LayoutDashboard, 'Market Intelligence'],
  ['/events', 'Changes & Events', Activity, 'Market Intelligence'],
  ['/market-data', 'Market Data', Database, 'Market Intelligence'],
  ['/reports', 'Reports', FileText, 'Market Intelligence'],
  ['/settings', 'Monitoring', Settings2, 'Monitoring'],
  ['/jobs', 'Job Status', ClipboardList, 'Monitoring']
] as const

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  return (
    <div className="theme-switch" aria-label="Color theme">
      <button
        aria-pressed={mounted && theme !== 'dark'}
        onClick={() => setTheme('light')}
      >
        <Sun size={15} />
        Light
      </button>
      <button
        aria-pressed={mounted && theme === 'dark'}
        onClick={() => setTheme('dark')}
      >
        <Moon size={15} />
        Dark
      </button>
    </div>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname()
  const params = useSearchParams()
  const router = useRouter()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [narrow, setNarrow] = useState(false)
  const sidebarRef = useRef<HTMLElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px)')
    const update = () => setNarrow(media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    if (!mobileOpen || !narrow) return
    const trigger = triggerRef.current
    sidebarRef.current?.querySelector<HTMLElement>('a,button')?.focus()
    return () => trigger?.focus()
  }, [mobileOpen, narrow])
  const [search, setSearch] = useState('')
  const hydrated = useStore((s) => s.hydrated)
  const endpoint = useStore((s) => s.selectedEndpoint)
  const auth = useStore((s) => s.authToken)
  const streaming = useStore((s) => s.isStreaming)
  const active = useStore((s) => s.isEndpointActive)
  const loading = useStore((s) => s.isEndpointLoading)
  const { initialize, focusChatInput } = useChatActions()
  const initKey = useRef('')
  useEffect(() => {
    const key = `${endpoint}|${auth}|${params.get('agent') || params.get('team') || ''}|${params.get('db_id') || ''}`
    if (hydrated && initKey.current !== key) {
      initKey.current = key
      void initialize()
    }
  }, [hydrated, endpoint, auth, initialize, params])
  useEffect(() => setMobileOpen(false), [path, params])
  const query = params.toString()
  const lastChatQuery = useRef(query)
  useEffect(() => {
    if (path === '/' || path === '/chat') lastChatQuery.current = query
  }, [path, query])
  const href = (target: string) =>
    `${target}?${target === '/' && path !== '/' && path !== '/chat' ? lastChatQuery.current : query}`
  const newChat = () => {
    if (streaming) return
    useStore.getState().setMessages([])
    useStore.getState().resetComposer()
    useStore.getState().setStreamingErrorMessage('')
    useStore.getState().setSessionLoad({ id: null, status: 'idle', error: '' })
    const next = new URLSearchParams(query)
    for (const key of ['session', 'context', 'record']) next.delete(key)
    lastChatQuery.current = next.toString()
    router.push(`/?${next}`)
    setMobileOpen(false)
    focusChatInput()
  }
  return (
    <div
      className={`workspace ${collapsed ? 'sidebar-collapsed' : ''} ${mobileOpen ? 'sidebar-open' : ''}`}
    >
      {mobileOpen && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        ref={sidebarRef}
        className="workspace-sidebar"
        aria-label="Workspace navigation"
        inert={narrow && !mobileOpen ? true : undefined}
        onKeyDown={(e) => {
          if (!narrow || !mobileOpen) return
          if (e.key === 'Escape') setMobileOpen(false)
          if (e.key === 'Tab') {
            const items = Array.from(
              sidebarRef.current?.querySelectorAll<HTMLElement>(
                'a[href],button:not([disabled]),input,summary'
              ) || []
            ).filter((node) => node.getClientRects().length)
            const first = items[0],
              last = items[items.length - 1]
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault()
              last?.focus()
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault()
              first?.focus()
            }
          }
        }}
      >
        <div className="sidebar-brand">
          <Building2 size={23} />
          <Link href={href('/')}>
            DeepInsight Lite<span>London Office Intelligence</span>
          </Link>
          <button
            className="icon-button desktop-only"
            aria-label="Collapse sidebar"
            onClick={() => setCollapsed(true)}
          >
            <PanelLeft size={18} />
          </button>
          <button
            className="icon-button mobile-only"
            aria-label="Close sidebar"
            onClick={() => setMobileOpen(false)}
          >
            <X size={18} />
          </button>
        </div>
        <button className="new-chat" disabled={streaming} onClick={newChat}>
          <SquarePen size={18} />
          New chat
        </button>
        <label className="session-search">
          <Search size={16} />
          <input
            aria-label="Search conversation titles"
            placeholder="Search conversation titles"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <nav aria-label="Workspace sections">
          {['AI Workspace', 'Market Intelligence', 'Monitoring'].map(
            (group) => (
              <div key={group}>
                <p className="nav-label">{group}</p>
                {navigation
                  .filter((item) => item[3] === group)
                  .map(([target, label, Icon]) => (
                    <Link
                      key={target}
                      href={href(target)}
                      aria-current={
                        path === target ||
                        (target === '/' &&
                          (path === '/chat' || path === '/ask'))
                          ? 'page'
                          : undefined
                      }
                    >
                      <Icon size={17} />
                      {label}
                    </Link>
                  ))}
              </div>
            )
          )}
        </nav>
        <div className="recent-chats">
          <Sessions search={search} />
        </div>
        <div className="sidebar-bottom">
          <ThemeToggle />
          <details className="connection-settings">
            <summary>Connection settings</summary>
            <p className="break-all">{endpoint}</p>
            <AuthToken
              hasEnvToken={!!process.env.NEXT_PUBLIC_OS_SECURITY_KEY}
              envToken={process.env.NEXT_PUBLIC_OS_SECURITY_KEY || ''}
            />
          </details>
        </div>
      </aside>
      <div
        className="workspace-main"
        inert={mobileOpen && narrow ? true : undefined}
      >
        <header className="workspace-toolbar">
          <div className="flex min-w-0 items-center gap-3">
            <button
              ref={triggerRef}
              className={`icon-button ${collapsed ? '' : 'mobile-only'}`}
              aria-label="Open sidebar"
              onClick={() => {
                setCollapsed(false)
                setMobileOpen(true)
              }}
            >
              <PanelLeft size={19} />
            </button>
            <span>London Office Intelligence</span>
          </div>
          <span className="connection-state">
            <i className={active ? 'online' : ''} />
            {loading
              ? 'Connecting…'
              : active
                ? 'AI service connected'
                : 'AI service unavailable'}
          </span>
        </header>
        <div className="workspace-content">{children}</div>
      </div>
    </div>
  )
}

export default function WorkspaceShell({
  children
}: {
  children: React.ReactNode
}) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      storageKey="london-office-theme"
    >
      <Shell>{children}</Shell>
      <Toaster />
    </ThemeProvider>
  )
}
