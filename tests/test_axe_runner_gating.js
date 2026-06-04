// Gating-tag and skip-condition tests for axe_runner.js.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main, EXIT } = require(path.join(__dirname, '..', 'hooks', '_lib', 'axe_runner.js'));
const { makeCleanResult, makeWcag2aaResult, withA11yEnv } = require('./_helpers/axe_runner_stubs.js');

test('run_main exports and EXIT codes present', () => {
  assert.strictEqual(typeof run_main, 'function');
  assert.strictEqual(EXIT.ok, 0);
  assert.strictEqual(EXIT.failed, 1);
  assert.strictEqual(EXIT.skipped, 2);
});

test('run_main with wcag2aa stub violation returns EXIT.failed', async () => {
  const code = await run_main(['--url', 'http://localhost:3000/'], { axeRunFn: async () => makeWcag2aaResult() });
  assert.strictEqual(code, EXIT.failed);
});

test('run_main with zero violations returns EXIT.ok', async () => {
  const code = await run_main(['--url', 'http://localhost:3000/'], { axeRunFn: async () => makeCleanResult() });
  assert.strictEqual(code, EXIT.ok);
});

test('run_main gates on wcag2a tagged violation', async () => {
  const code = await run_main(['--url', 'http://localhost:3000/'], {
    axeRunFn: async () => ({ violations: [{ id: 'image-alt', tags: ['wcag2a'], help: 'Add alt text', nodes: [{ target: 'img', html: '<img>' }] }], incomplete: [] }),
  });
  assert.strictEqual(code, EXIT.failed);
});

test('run_main gates on wcag21aa tagged violation', async () => {
  const code = await run_main(['--url', 'http://localhost:3000/'], {
    axeRunFn: async () => ({ violations: [{ id: 'focus-visible', tags: ['wcag21aa'], help: 'Focus visible', nodes: [{ target: 'a', html: '<a>' }] }], incomplete: [] }),
  });
  assert.strictEqual(code, EXIT.failed);
});

test('run_main gates on wcag21a tagged violation', async () => {
  const code = await run_main(['--url', 'http://localhost:3000/'], {
    axeRunFn: async () => ({ violations: [{ id: 'label', tags: ['wcag21a'], help: 'Label', nodes: [{ target: 'input', html: '<input>' }] }], incomplete: [] }),
  });
  assert.strictEqual(code, EXIT.failed);
});

test('run_main with best-practice-only violation returns EXIT.ok', async () => {
  const code = await run_main(['--url', 'http://localhost:3000/'], {
    axeRunFn: async () => ({ violations: [{ id: 'skip-link', tags: ['best-practice'], help: 'Add skip link', nodes: [{ target: 'body', html: '<body>' }] }], incomplete: [] }),
  });
  assert.strictEqual(code, EXIT.ok);
});

test('run_main with only incomplete results returns EXIT.ok', async () => {
  const code = await run_main(['--url', 'http://localhost:3000/'], {
    axeRunFn: async () => ({ violations: [], incomplete: [{ id: 'color-contrast', tags: ['wcag2aa'], help: 'Needs review', nodes: [] }] }),
  });
  assert.strictEqual(code, EXIT.ok);
});

test('run_main with CLAUDE_A11Y=0 returns EXIT.skipped', async () => {
  const code = await withA11yEnv('0', () => run_main(['--url', 'http://localhost:3000/'], { axeRunFn: async () => makeWcag2aaResult() }));
  assert.strictEqual(code, EXIT.skipped);
});

test('run_main with axeRunFn throwing returns EXIT.skipped', async () => {
  const code = await run_main(['--url', 'http://localhost:3000/'], {
    axeRunFn: async () => { throw new Error('browser-launch-failed'); },
  });
  assert.strictEqual(code, EXIT.skipped);
});
