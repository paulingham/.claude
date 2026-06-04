// Spec-blind: json-shape-failed, json-skip-reason-field tests.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main } = require(path.join(__dirname, '..', '..', 'hooks', '_lib', 'axe_runner.js'));
const { cleanAxeResult, violationResult, captureStdoutJSON, withEnvVar } = require('./_axe_runner_helpers.js');

test('AC-json-shape-failed: stdout JSON has required fields on gating violation', async () => {
  const output = await captureStdoutJSON(() =>
    run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => violationResult(['wcag2aa']) }),
  );
  assert.ok('verdict' in output);
  assert.ok(Array.isArray(output.gating_violations));
  assert.ok(Array.isArray(output.incomplete));
  assert.ok(Array.isArray(output.routes));
  assert.strictEqual(output.verdict, 'A11Y_CHECK_FAILED');
  assert.ok(output.gating_violations.length > 0);
});

test('AC-json-skip-reason-field: stdout JSON has skip_reason when skipped', async () => {
  const output = await captureStdoutJSON(() =>
    withEnvVar('CLAUDE_A11Y', '0', () =>
      run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() }),
    ),
  );
  assert.strictEqual(output.verdict, 'A11Y_CHECK_SKIPPED');
  assert.ok('skip_reason' in output, 'skip_reason must be present when verdict is A11Y_CHECK_SKIPPED');
  assert.strictEqual(output.skip_reason, 'env-hatch');
  assert.ok(Array.isArray(output.gating_violations), 'SKIPPED output must have gating_violations array');
});
