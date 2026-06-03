// CLI dependency resolver for axe_runner.js standalone mode.
// DI-testable: requireFn and readFileFn are injectable.
'use strict';
const path = require('node:path');
const fs = require('node:fs');

// Attempt to resolve playwright/playwright-core and axe-core from candidate dirs.
function _resolve_cli_deps(candidates, requireFn, readFileFn) {
  for (const base of candidates) {
    try {
      const playwrightPath = path.join(base, 'node_modules', 'playwright');
      const playwrightCorePath = path.join(base, 'node_modules', 'playwright-core');
      const axePath = path.join(base, 'node_modules', 'axe-core', 'axe.min.js');
      const pwPath = fs.existsSync(playwrightPath) ? playwrightPath : playwrightCorePath;
      const pw = requireFn(pwPath);
      const axeSource = readFileFn(axePath, 'utf8');
      return { chromium: pw.chromium, axeSource };
    } catch (_) {
      // try next candidate
    }
  }
  return null;
}

// Build an axeRunFn from a resolved chromium launcher and axe source string.
function _make_axe_run_fn(chromium, axeSource) {
  return async function axeRunFn(url) {
    const browser = await chromium.launch({ headless: true });
    try {
      const page = await browser.newPage();
      await page.goto(url);
      await page.addScriptTag({ content: axeSource });
      return await page.evaluate(() => window.axe.run(document, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] },
      }));
    } finally {
      await browser.close();
    }
  };
}

module.exports = { _resolve_cli_deps, _make_axe_run_fn };
