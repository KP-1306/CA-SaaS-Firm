import { resolve } from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

/**
 * Two independent application entry points.
 *
 * The internal and portal planes are structurally separate (AR §2.4, ADR-004):
 * they build to separate bundles, mount separate roots and share no
 * authentication state. Only neutral infrastructure under `src/shared` is
 * common to both.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@shared': resolve(__dirname, 'src/shared'),
      '@features': resolve(__dirname, 'src/features'),
      '@api': resolve(__dirname, 'src/api'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        internal: resolve(__dirname, 'internal.html'),
        portal: resolve(__dirname, 'portal.html'),
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
