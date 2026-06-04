// Spec-blind: incomplete, env-hatch, env-hygiene, throw-skipped tests.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main, EXIT } = require(path.join(__dirname, '..', '..', 'hooks', '_lib', 'axe_runner.js'));
const { cleanAxeResult, withEnvVar } = require('./_axe_runner_helpers.js');

test('AC-incomplete-never-gates: incomplete wcag2aa result returns EXIT.ok', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], {
    axeRunFn: async () => ({ violations: [], incomplete: [{ id: 'color-contrast', tags: ['wcag2aa'], help: 'Review needed', nodes: [] }] }),
  });
  assert.strictEqual(code, EXIT.ok);
});

test('AC-env-hatch: CLAUDE_A11Y=0 returns EXIT.skipped', async () => {
  const code = await withEnvVar('CLAUDE_A11Y', '0', () =>
    run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() }),
  );
  assert.strictEqual(code, EXIT.skipped);
});

test('AC-env-hygiene: CLAUDE_A11Y restored after env-hatch test', async () => {
  await withEnvVar('CLAUDE_A11Y', '0', () =>
    run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() }),
  );
  const code = await run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() });
  assert.strictEqual(code, EXIT.ok, 'CLAUDE_A11Y env var must be cleaned up after env-hatch test');
});

test('AC-throw-skipped: axeRunFn throwing returns EXIT.skipped', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], {
    axeRunFn: async () => { throw new Error('browser-launch-failed'); },
  });
  assert.strictEqual(code, EXIT.skipped);
});
