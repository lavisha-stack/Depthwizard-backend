import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return ({
    plugins: [react()],
    resolve: {
      alias: [
        { find: /^three$/, replacement: path.resolve(process.cwd(), 'node_modules/three/build/three.module.js') },
        { find: /^three\/addons\/(.*)$/, replacement: `${path.resolve(process.cwd(), 'node_modules/three/examples/jsm')}/$1` },
      ],
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      fs: { allow: ['..'] },
      proxy: {
        // Serve result assets through the frontend origin during development.
        // This avoids browser/WebGL cross-origin texture restrictions.
        '/api': { target: env.VITE_API_BASE_URL || 'http://127.0.0.1:8000', changeOrigin: true },
      },
    },
    build: {
      // Three.js is lazy-loaded only on the results page. Its minified chunk is
      // ~509 kB (~130 kB gzip), so use an explicit threshold for this known asset.
      chunkSizeWarningLimit: 550,
    },
  })
})
