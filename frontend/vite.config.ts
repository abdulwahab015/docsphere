import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    // Must match the backend's FRONTEND_URL / CORS_ALLOWED_ORIGINS, and the
    // links it puts in emails (invite accept, password reset, billing return).
    port: 3000,
    strictPort: true,
  },
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          // The React runtime and router are needed by every page and change
          // only on upgrades, so a chunk of their own stays cached across
          // releases. The rest is split with the pages that use it.
          groups: [
            {
              name: 'react',
              test: /[\\/]node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/,
            },
          ],
        },
      },
    },
  },
  preview: {
    port: 3000,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    // Playwright owns e2e/; Vitest runs only the unit/component tests in src/.
    include: ['src/**/*.test.{ts,tsx}'],
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // Interaction-heavy tests (typing into several fields) take ~1-2s but spiked
    // past the 5s default under full parallel load with coverage; CI runners
    // have fewer cores. A real hang still fails quickly enough.
    testTimeout: 15_000,
    env: {
      VITE_API_BASE_URL: 'http://api.test',
    },
    css: false,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/api/schema.d.ts',
        'src/components/ui/**',
        'src/main.tsx',
      ],
      // Same bar as the backend's .coveragerc fail_under.
      thresholds: {
        lines: 95,
        functions: 95,
        branches: 95,
        statements: 95,
      },
    },
  },
})
