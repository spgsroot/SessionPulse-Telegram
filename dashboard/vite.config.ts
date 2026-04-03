import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api/': {
        target: 'http://session-pulse:8500',
        changeOrigin: true
      },
      '/healthz': {
        target: 'http://session-pulse:8500',
        changeOrigin: true
      }
    }
  }
});
