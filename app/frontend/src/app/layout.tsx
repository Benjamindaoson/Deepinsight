import type { Metadata } from 'next'
import { NuqsAdapter } from 'nuqs/adapters/next/app'
import './globals.css'
import { Suspense } from 'react'
import WorkspaceShell from '@/components/workspace/WorkspaceShell'

export const metadata: Metadata = {
  title: 'DeepInsight Lite · London Office Intelligence',
  description:
    'Evidence-backed London office market monitoring, source records, reports, and native AgentOS chat.'
}

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased">
        <NuqsAdapter>
          <Suspense fallback={<div className="p-8">Loading workspace…</div>}>
            <WorkspaceShell>{children}</WorkspaceShell>
          </Suspense>
        </NuqsAdapter>
      </body>
    </html>
  )
}
