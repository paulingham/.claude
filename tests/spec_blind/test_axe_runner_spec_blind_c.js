// Spec-blind: throw-skip-reason, zero-url-throws, json-shape-passed tests.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main } = require(path.join(__dirname, '..', '..', 'hooks', '_lib', 'axe_runner.js'));
const { cleanAxeResult, captureStdoutJSON } = require('./_axe_runner_helpers.js');

test('AC-throw-skip-reason: axeRunFn throwing emits skip_reason in JSON', async () => {
  const output = await captureStdoutJSON(() =>
    run_main(['--url', 'http://localhost:9999/'], {
      axeRunFn: async () => { throw new Error('browser-launch-failed'); },
    }),
  );
  assert.ok('skip_reason' in output, 'skip_reason must be present in stdout JSON when thrown');
  const validSkipReasons = ['no-dev-server-contract', 'browser-launch-failed', 'env-hatch'];
  assert.ok(validSkipReasons.includes(output.skip_reason), `skip_reason must be one of ${validSkipReasons.join(', ')}, got: ${output.skip_reason}`);
});

test('AC-zero-url-throws: zero --url flags causes run_main to throw', async () => {
  await assert.rejects(
    () => run_main([], { axeRunFn: async () => cleanAxeResult() }),
    /at least one --url/i,
    'run_main must throw when no --url flags are provided',
  );
});

test('AC-json-shape-passed: stdout JSON has required fields on clean run', async () => {
  const output = await captureStdoutJSON(() =>
    run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() }),
  );
  assert.ok('verdict' in output, 'must have verdict');
  assert.ok(Array.isArray(output.gating_violations), 'must have gating_violations[]');
  assert.ok(Array.isArray(output.incomplete), 'must have incomplete[]');
  assert.ok(Array.isArray(output.routes), 'must have routes[]');
  assert.strictEqual(output.verdict, 'A11Y_CHECK_PASSED');
  assert.strictEqual(output.gating_violations.length, 0);
});
