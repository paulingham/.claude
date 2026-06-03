// Spec-blind: exports and GATING_TAGS gate tests.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main, EXIT } = require(path.join(__dirname, '..', '..', 'hooks', '_lib', 'axe_runner.js'));
const { cleanAxeResult, violationResult } = require('./_axe_runner_helpers.js');

test('AC-exports: run_main is a function and EXIT codes are 0/1/2', () => {
  assert.strictEqual(typeof run_main, 'function', 'run_main must be a function');
  assert.strictEqual(EXIT.ok, 0, 'EXIT.ok must be 0');
  assert.strictEqual(EXIT.failed, 1, 'EXIT.failed must be 1');
  assert.strictEqual(EXIT.skipped, 2, 'EXIT.skipped must be 2');
});

test('AC-gating-wcag2aa: wcag2aa violation returns EXIT.failed', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => violationResult(['wcag2aa']) });
  assert.strictEqual(code, EXIT.failed);
});

test('AC-gating-wcag2a: wcag2a violation returns EXIT.failed', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => violationResult(['wcag2a']) });
  assert.strictEqual(code, EXIT.failed);
});

test('AC-gating-wcag21aa: wcag21aa violation returns EXIT.failed', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => violationResult(['wcag21aa']) });
  assert.strictEqual(code, EXIT.failed);
});

test('AC-gating-wcag21a: wcag21a violation returns EXIT.failed', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => violationResult(['wcag21a']) });
  assert.strictEqual(code, EXIT.failed);
});

test('AC-non-gating-best-practice: best-practice-only violation returns EXIT.ok', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => violationResult(['best-practice']) });
  assert.strictEqual(code, EXIT.ok);
});

test('AC-non-gating-experimental: experimental-only violation returns EXIT.ok', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => violationResult(['experimental']) });
  assert.strictEqual(code, EXIT.ok);
});

test('AC-clean: zero violations returns EXIT.ok', async () => {
  const code = await run_main(['--url', 'http://localhost:9999/'], { axeRunFn: async () => cleanAxeResult() });
  assert.strictEqual(code, EXIT.ok);
});
