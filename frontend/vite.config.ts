import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../outputs/frontend-dist-v2',
    emptyOutDir: false,
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    clearMocks: true,
  },
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
