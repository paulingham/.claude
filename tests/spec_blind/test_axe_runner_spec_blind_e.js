// Spec-blind: gating-violation-fields, multi-route tests.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main, EXIT } = require(path.join(__dirname, '..', '..', 'hooks', '_lib', 'axe_runner.js'));
const { cleanAxeResult, violationResult, captureStdoutJSON } = require('./_axe_runner_helpers.js');

test('AC-gating-violation-fields: gating_violations items have id, help, nodes with target+html', async () => {
  const output = await captureStdoutJSON(() =>
    run_main(['--url', 'http://localhost:9999/'], {
      axeRunFn: async () => ({ violations: [{ id: 'color-contrast', tags: ['wcag2aa'], help: 'Elements must have sufficient color contrast', nodes: [{ target: '.btn', html: '<button>Click</button>' }] }], incomplete: [] }),
    }),
  );
  assert.ok(output.gating_violations.length > 0);
  const gv = output.gating_violations[0];
  assert.ok('id' in gv && 'help' in gv && Array.isArray(gv.nodes) && gv.nodes.length > 0);
  assert.ok('target' in gv.nodes[0] && 'html' in gv.nodes[0]);
});

test('AC-multi-route-one-bad: one bad route among two yields EXIT.failed', async () => {
  let callCount = 0;
  const code = await run_main(
    ['--url', 'http://localhost:9999/', '--url', 'http://localhost:9999/dashboard'],
    { axeRunFn: async (url) => { callCount++; return url.includes('/dashboard') ? violationResult(['wcag2aa']) : cleanAxeResult(); } },
  );
  assert.strictEqual(code, EXIT.failed);
  assert.strictEqual(callCount, 2, 'axeRunFn must be called once per URL');
});

test('AC-multi-route-per-route-blocks: routes[] has per-route result blocks for all URLs', async () => {
  const output = await captureStdoutJSON(() =>
    run_main(['--url', 'http://localhost:9999/', '--url', 'http://localhost:9999/dashboard'], {
      axeRunFn: async (url) => url.includes('/dashboard') ? violationResult(['wcag2aa']) : cleanAxeResult(),
    }),
  );
  assert.strictEqual(output.routes.length, 2, 'routes[] must have one entry per scanned URL');
  const root = output.routes.find(r => !r.url.includes('/dashboard'));
  const dash = output.routes.find(r => r.url.includes('/dashboard'));
  assert.strictEqual(root.verdict, 'A11Y_CHECK_PASSED');
  assert.strictEqual(dash.verdict, 'A11Y_CHECK_FAILED');
});
