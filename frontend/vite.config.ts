import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { loadEnv, type Plugin } from 'vite'
import { defineConfig } from 'vitest/config'

import { nginxHeadersFile, pagesHeadersFile, securityHeaders } from './securityHeaders.ts'

function emitSecurityHeaders(apiBaseUrl: string): Plugin {
  return {
    name: 'emit-security-headers',
    apply: 'build',
    generateBundle() {
      const headers = securityHeaders(apiBaseUrl)
      this.emitFile({ type: 'asset', fileName: '_headers', source: pagesHeadersFile(headers) })
      this.emitFile({
        type: 'asset',
        fileName: 'nginx-security-headers.conf',
        source: nginxHeadersFile(headers),
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const apiBaseUrl = env.VITE_API_BASE_URL ?? 'http://localhost:8000'
  return {
    plugins: [react(), tailwindcss(), emitSecurityHeaders(apiBaseUrl)],
    server: { port: 5173 },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      include: ['src/**/*.test.{ts,tsx}'],
    },
  }
})
