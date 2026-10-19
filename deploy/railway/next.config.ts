import type { NextConfig } from 'next'

const backend = process.env.LONDON_BACKEND_PRIVATE_URL
if (process.env.NODE_ENV === 'production' && !backend) {
  throw new Error('LONDON_BACKEND_PRIVATE_URL is required')
}

const nextConfig: NextConfig = {
  devIndicators: false,
  distDir: process.env.DEEPINSIGHT_NEXT_DIST_DIR || '.next',
  async rewrites() {
    if (!backend) return []
    return {
      beforeFiles: [{ source: '/api/:path*', destination: `${backend}/api/:path*` }],
      afterFiles: [],
      fallback: [{ source: '/:path*', destination: `${backend}/:path*` }]
    }
  }
}

export default nextConfig
