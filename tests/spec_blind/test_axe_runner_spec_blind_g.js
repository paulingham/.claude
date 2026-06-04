// Spec-blind: skip-reason enum, incomplete-in-output, multi-route-all-clean tests.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main, EXIT } = require(path.join(__dirname, '..', '..', 'hooks', '_lib', 'axe_runner.js'));
const { cleanAxeResult, captureStdoutJSON, withEnvVar } = require('./_axe_runner_helpers.js');

test('AC-skip-reason-env-hatch: env-hatch produces skip_reason env-hatch', async () => {
  const output = await captureStdoutJSON(() =>
    withEnvVar('CLAUDE_A11Y', '0', () =>
      run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() }),
    ),
  );
  assert.strictEqual(output.skip_reason, 'env-hatch');
});

test('AC-skip-reason-browser-launch-failed: throw produces skip_reason browser-launch-failed', async () => {
  const output = await captureStdoutJSON(() =>
    run_main(['--url', 'http://localhost:9999/'], {
      axeRunFn: async () => { throw new Error('cannot launch browser'); },
    }),
  );
  assert.strictEqual(output.skip_reason, 'browser-launch-failed');
});

test('AC-incomplete-in-output: incomplete results appear in incomplete[] not gating_violations', async () => {
  const output = await captureStdoutJSON(() =>
    run_main(['--url', 'http://localhost:9999/'], {
      axeRunFn: async () => ({ violations: [], incomplete: [{ id: 'color-contrast', tags: ['wcag2aa'], help: 'Needs review', nodes: [{ target: '.x', html: '<div>' }] }] }),
    }),
  );
  assert.strictEqual(output.verdict, 'A11Y_CHECK_PASSED');
  assert.strictEqual(output.gating_violations.length, 0);
  assert.ok(Array.isArray(output.incomplete));
});

test('AC-multi-route-all-clean: all clean routes yields EXIT.ok', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:9999/', '--url', 'http://localhost:9999/about'],
    { axeRunFn: async () => cleanAxeResult() },
  );
  assert.strictEqual(code, EXIT.ok);
});
