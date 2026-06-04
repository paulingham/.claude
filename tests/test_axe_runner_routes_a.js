// Output shape tests for axe_runner.js (contract fields + HTML sanitization).
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main } = require(path.join(__dirname, '..', 'hooks', '_lib', 'axe_runner.js'));
const { makeCleanResult, makeWcag2aaResult, captureStdout } = require('./_helpers/axe_runner_stubs.js');

test('run_main output JSON shape matches contract', async () => {
  const output = await captureStdout(() => run_main(['--url', 'http://localhost:3000/'], { axeRunFn: async () => makeCleanResult() }));
  assert.ok('verdict' in output, 'must have verdict');
  assert.ok(Array.isArray(output.gating_violations), 'must have gating_violations array');
  assert.ok(Array.isArray(output.incomplete), 'must have incomplete array');
  assert.ok(Array.isArray(output.routes), 'must have routes array');
  assert.ok(!('violations' in output), 'must NOT have duplicate violations field');
});

test('run_main gating_violations items have actionability fields', async () => {
  const output = await captureStdout(() => run_main(['--url', 'http://localhost:3000/'], {
    axeRunFn: async () => ({ violations: [{ id: 'color-contrast', tags: ['wcag2aa'], help: 'Fix contrast', nodes: [{ target: '.btn', html: '<button>' }] }], incomplete: [] }),
  }));
  assert.ok(output.gating_violations.length > 0, 'gating_violations must be non-empty');
  const gv = output.gating_violations[0];
  assert.ok('id' in gv && 'help' in gv && Array.isArray(gv.nodes));
  assert.ok('target' in gv.nodes[0] && 'html' in gv.nodes[0]);
});

test('run_main nodes html is truncated and HTML-encoded', async () => {
  const longHtml = '<div class="x">' + 'a'.repeat(600) + '</div>';
  const output = await captureStdout(() => run_main(['--url', 'http://localhost:3000/'], {
    axeRunFn: async () => ({ violations: [{ id: 'test', tags: ['wcag2a'], help: 'h', nodes: [{ target: 'div', html: longHtml }] }], incomplete: [] }),
  }));
  const html = output.gating_violations[0].nodes[0].html;
  assert.ok(html.length <= 500, `html must be truncated to ≤500 chars, got ${html.length}`);
  assert.ok(html.includes('&lt;'), 'html must be HTML-encoded');
});

test('run_main always includes root route', async () => {
  const output = await captureStdout(() => run_main(['--url', '/'], { axeRunFn: async () => makeCleanResult() }));
  assert.strictEqual(output.routes.length, 1);
  assert.strictEqual(output.routes[0].url, '/');
});

