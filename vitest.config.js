import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { include: ['tests/**/*.test.js'], environment: 'jsdom',
  coverage: { provider: 'v8', include: ['app/web/**/*.js', 'tools/**/*.js', 'vitest.config.js', 'playwright.config.js'], reporter: ['text', 'json', 'html'],
    thresholds: { statements: 100, branches: 100, functions: 100, lines: 100 } } } });
