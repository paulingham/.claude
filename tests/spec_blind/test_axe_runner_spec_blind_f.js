// Spec-blind: root-only, verdict-enum, exit-code mapping tests.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main, EXIT } = require(path.join(__dirname, '..', '..', 'hooks', '_lib', 'axe_runner.js'));
const { cleanAxeResult, violationResult, captureStdoutJSON, withEnvVar } = require('./_axe_runner_helpers.js');

test('AC-root-only: single "/" URL scan succeeds and routes[] contains root', async () => {
  const output = await captureStdoutJSON(() =>
    run_main(['--url', '/'], { axeRunFn: async () => cleanAxeResult() }),
  );
  assert.strictEqual(output.routes.length, 1);
  assert.strictEqual(output.routes[0].url, '/');
  assert.strictEqual(output.verdict, 'A11Y_CHECK_PASSED');
});

test('AC-verdict-enum-passed: verdict is A11Y_CHECK_PASSED for clean run', async () => {
  const output = await captureStdoutJSON(() =>
    run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() }),
  );
  assert.strictEqual(output.verdict, 'A11Y_CHECK_PASSED');
});

test('AC-verdict-enum-failed: verdict is A11Y_CHECK_FAILED for gating violation', async () => {
  const output = await captureStdoutJSON(() =>
    run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => violationResult(['wcag2aa']) }),
  );
  assert.strictEqual(output.verdict, 'A11Y_CHECK_FAILED');
});

test('AC-verdict-enum-skipped: verdict is A11Y_CHECK_SKIPPED for env-hatch', async () => {
  const output = await captureStdoutJSON(() =>
    withEnvVar('CLAUDE_A11Y', '0', () =>
      run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() }),
    ),
  );
  assert.strictEqual(output.verdict, 'A11Y_CHECK_SKIPPED');
});

