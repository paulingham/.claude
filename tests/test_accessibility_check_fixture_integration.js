// Fixture integration test — runs real axe-core against file:// URLs.
// Deps acquired at runtime into tests/fixtures/accessibility-check/.deps/
// CLAUDE_A11Y_FIXTURE_SKIP=1 skips the test with a printed reason.
// Dep acquisition failure = FAIL (loud), not skip.

'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { execSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');

const repoRoot = path.resolve(__dirname, '..');
const fixtureDir = path.join(repoRoot, 'tests', 'fixtures', 'accessibility-check');
const depsDir = path.join(fixtureDir, '.deps');
const violationsHtml = path.join(fixtureDir, 'violations.html');
const fixedHtml = path.join(fixtureDir, 'fixed.html');

// SKIP hatch
if (process.env.CLAUDE_A11Y_FIXTURE_SKIP === '1') {
  console.log('# SKIP: CLAUDE_A11Y_FIXTURE_SKIP=1 set — skipping fixture integration tests');
  process.exit(0);
}

// Acquire deps at runtime
function acquireDeps() {
  fs.mkdirSync(depsDir, { recursive: true });
  // Write a minimal package.json in the deps dir so npm install scopes here
  const pkgPath = path.join(depsDir, 'package.json');
  if (!fs.existsSync(pkgPath)) {
    fs.writeFileSync(pkgPath, JSON.stringify({ name: 'a11y-fixture-deps', private: true }));
  }
  const result = spawnSync(
    'npm',
    ['install', '--prefix', depsDir, 'axe-core', 'playwright'],
    { encoding: 'utf8', timeout: 120000 },
  );
  if (result.status !== 0) {
    process.stderr.write('FAIL: dep acquisition failed for fixture integration tests\n');
    process.stderr.write(result.stderr || '');
    process.stderr.write(result.stdout || '');
    throw new Error(`npm install failed with status ${result.status}`);
  }
}

acquireDeps();

// Load playwright after installation
const playwrightPath = path.join(depsDir, 'node_modules', 'playwright');
const axeCorePath = path.join(depsDir, 'node_modules', 'axe-core', 'axe.min.js');

const { chromium } = require(playwrightPath);
const axeSource = fs.readFileSync(axeCorePath, 'utf8');

async function runAxeOnFile(htmlFilePath) {
  const fileUrl = 'file://' + htmlFilePath;
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(fileUrl);
    await page.addScriptTag({ content: axeSource });
    const results = await page.evaluate(() => {
      return window.axe.run(document, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] },
      });
    });
    const GATING_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
    const gatingViolations = results.violations.filter(v =>
      v.tags.some(tag => GATING_TAGS.includes(tag)),
    );
    return {
      verdict: gatingViolations.length > 0 ? 'A11Y_CHECK_FAILED' : 'A11Y_CHECK_PASSED',
      gating_violations: gatingViolations,
      incomplete: results.incomplete,
    };
  } finally {
    await browser.close();
  }
}

test('fixture violations_html produces A11Y_CHECK_FAILED', async () => {
  const result = await runAxeOnFile(violationsHtml);
  assert.strictEqual(
    result.verdict,
    'A11Y_CHECK_FAILED',
    `Expected A11Y_CHECK_FAILED but got ${result.verdict}. Gating violations: ${JSON.stringify(result.gating_violations)}`,
  );
  assert.ok(result.gating_violations.length > 0, 'must have at least one gating violation');
});

test('fixture fixed_html produces A11Y_CHECK_PASSED', async () => {
  const result = await runAxeOnFile(fixedHtml);
  assert.strictEqual(
    result.verdict,
    'A11Y_CHECK_PASSED',
    `Expected A11Y_CHECK_PASSED but got ${result.verdict}. Gating violations: ${JSON.stringify(result.gating_violations)}`,
  );
  assert.strictEqual(result.gating_violations.length, 0, 'fixed.html must have zero gating violations');
});
