import { defineConfig, mergeConfig } from 'vitest/config';

import viteConfig from './vite.config';

// Inherit Vite's resolve.alias (the single authoritative alias contract) so
// that @shared/@features/@api resolve identically in tests, dev and build.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./tests/setup.ts'],
      include: ['tests/**/*.test.{ts,tsx}'],
    },
  }),
);
