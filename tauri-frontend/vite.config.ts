import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    allowedHosts: true,
    // Termux/Android no soporta inotify nativo — usar polling
    watch: {
      usePolling: true,
      interval: 2000,
      ignored: [
        '**/node_modules/**',
        '**/.git/**',
        '**/dist/**',
        '**/.cargo/**',
      ],
    },
    proxy: {
      '/api':      { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/canary':   { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/ws':       { target: 'ws://127.0.0.1:8001',   ws: true },
      '/assets':   { target: 'http://127.0.0.1:8001', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
        },
      },
    },
  },
  optimizeDeps: {
    force: false,
  },
});
