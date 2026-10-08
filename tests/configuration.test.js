import {it, expect} from 'vitest';
import unit from '../vitest.config.js';
import browser from '../playwright.config.js';

it('measures nested and unimported first-party modules and keeps browser traces private',()=>{
  expect(unit.test.coverage.include).toContain('app/web/**/*.js');
  expect(unit.test.coverage.include).toContain('tools/**/*.js');
  expect(unit.test.coverage.thresholds).toEqual({statements:100,branches:100,functions:100,lines:100});
  expect(browser.outputDir).toBe('test-results');
  expect(browser.use.trace).toBe('retain-on-failure');
});
