import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/flood-detection': 'http://localhost:8000',
      '/jobs': 'http://localhost:8000',
      '/flood-mask': 'http://localhost:8000',
      '/districts': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
});
