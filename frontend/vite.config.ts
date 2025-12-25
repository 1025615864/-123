import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(() => {
  const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'
  const wsProxyTarget = process.env.VITE_WS_PROXY_TARGET || proxyTarget.replace(/^http/, 'ws')

  return {
    plugins: [react()],
    resolve: {
      dedupe: ['react', 'react-dom'],
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
        '/ws': {
          target: wsProxyTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  }
})
