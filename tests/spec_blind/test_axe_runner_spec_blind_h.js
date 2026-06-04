// Spec-blind: exit-code mapping tests.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main } = require(path.join(__dirname, '..', '..', 'hooks', '_lib', 'axe_runner.js'));
const { cleanAxeResult, violationResult, withEnvVar } = require('./_axe_runner_helpers.js');

test('AC-exit-code-clean: EXIT.ok (0) returned for clean run', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() });
  assert.strictEqual(code, 0);
});

test('AC-exit-code-failed: EXIT.failed (1) returned for gating violation', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => violationResult(['wcag2aa']) });
  assert.strictEqual(code, 1);
});

test('AC-exit-code-skipped: EXIT.skipped (2) returned for env-hatch', async () => {
  const code = await withEnvVar('CLAUDE_A11Y', '0', () =>
    run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() }),
  );
  assert.strictEqual(code, 2);
});
