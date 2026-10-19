import { NextRequest, NextResponse } from 'next/server'

function equal(a: string, b: string): boolean {
  const len = Math.max(a.length, b.length)
  let diff = a.length ^ b.length
  for (let i = 0; i < len; i++) diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0)
  return diff === 0
}

export function middleware(request: NextRequest) {
  const password = process.env.LONDON_SITE_PASSWORD
  if (!password) return new Response('Site access is not configured', { status: 503 })
  const auth = request.headers.get('authorization') || ''
  let supplied = ''
  try {
    if (auth.startsWith('Basic ')) {
      const pair = atob(auth.slice(6))
      const i = pair.indexOf(':')
      if (i >= 0 && pair.slice(0, i) === 'reviewer') supplied = pair.slice(i + 1)
    }
  } catch {}
  if (!equal(supplied, password)) {
    return new Response('Authentication required', {
      status: 401,
      headers: {
        'WWW-Authenticate': 'Basic realm="DeepInsight Lite", charset="UTF-8"',
        'Cache-Control': 'no-store'
      }
    })
  }
  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)']
}
