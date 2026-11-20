/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// PWA: installable, offline static-asset caching, push-ready (TS Cl. 2.10; FRD NFR-07)
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Grid-India Operations Management System',
        short_name: 'Grid-India OMS',
        description: 'Pan-Grid-India OMS for NLDC and RLDCs',
        theme_color: '#0b3a6e',
        background_color: '#ffffff',
        display: 'standalone',
        icons: [{ src: 'favicon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,woff2}'],
        navigateFallbackDenylist: [/^\/api/, /^\/graphql/, /^\/ws/],
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/graphql': 'http://127.0.0.1:8000',
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
  build: { chunkSizeWarningLimit: 2500 },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], globals: true },
})
