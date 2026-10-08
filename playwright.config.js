import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './tests/e2e', timeout: 30000, fullyParallel: true,
  workers: 2, reporter: [['list']], use: {browserName: 'chromium', trace: 'retain-on-failure'},
  outputDir: 'test-results' });
