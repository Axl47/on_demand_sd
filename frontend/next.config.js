/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  env: {
    DISPATCHER_URL: process.env.DISPATCHER_URL || 'http://localhost:8187',
    JWT_SECRET: process.env.JWT_SECRET || 'change-this-secret-key',
    AUTH_PASSWORD: process.env.AUTH_PASSWORD || 'comfyui123',
    GCE_COMFYUI_URL: process.env.GCE_COMFYUI_URL || 'http://localhost:8188',
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN'
          },
        ],
      },
    ]
  },
}

module.exports = nextConfig