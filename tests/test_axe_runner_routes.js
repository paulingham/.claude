// Output-shape and multi-route tests for axe_runner.js.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main, EXIT } = require(path.join(__dirname, '..', 'hooks', '_lib', 'axe_runner.js'));
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

test('run_main multi-route: callCount===2, per-route verdicts correct', async () => {
  let callCount = 0;
  const output = await captureStdout(() => run_main(
    ['--url', 'http://localhost:3000/', '--url', 'http://localhost:3000/dashboard'],
    {
      axeRunFn: async (url) => {
        callCount++;
        return url.includes('/dashboard') ? makeWcag2aaResult() : makeCleanResult();
      },
    },
  ));
  assert.strictEqual(callCount, 2, 'axeRunFn must be called once per route');
  assert.strictEqual(output.routes.length, 2);
  assert.strictEqual(output.routes[0].verdict, 'A11Y_CHECK_PASSED');
  assert.strictEqual(output.routes[1].verdict, 'A11Y_CHECK_FAILED');
});

test('run_main always includes root route', async () => {
  const output = await captureStdout(() => run_main(['--url', '/'], { axeRunFn: async () => makeCleanResult() }));
  assert.strictEqual(output.routes.length, 1);
  assert.strictEqual(output.routes[0].url, '/');
});

test('run_main multi-route one bad route yields EXIT.failed exit code', async () => {
  const chunks = [];
  const orig = process.stdout.write.bind(process.stdout);
  process.stdout.write = chunk => { chunks.push(chunk); return true; };
  let code;
  try {
    code = await run_main(
      ['--url', 'http://localhost:3000/', '--url', 'http://localhost:3000/bad'],
      {
        axeRunFn: async (url) =>
          url.includes('/bad') ? makeWcag2aaResult() : makeCleanResult(),
      },
    );
  } finally {
    process.stdout.write = orig;
  }
  assert.strictEqual(code, EXIT.failed, 'multi-route with one bad route must return EXIT.failed');
});

test('run_main gating_violations items carry route_url field', async () => {
  const output = await captureStdout(() => run_main(
    ['--url', 'http://localhost:3000/page'],
    { axeRunFn: async () => makeWcag2aaResult() },
  ));
  assert.ok(output.gating_violations.length > 0, 'must have gating_violations');
  assert.strictEqual(
    output.gating_violations[0].route_url,
    'http://localhost:3000/page',
    'gating_violations item must carry route_url matching the scanned URL',
  );
});

test('run_main skipped output carries skip_reason field', async () => {
  const chunks = [];
  const orig = process.stdout.write.bind(process.stdout);
  process.stdout.write = chunk => { chunks.push(chunk); return true; };
  let code;
  try {
    code = await run_main(
      ['--url', 'http://localhost:3000/'],
      { axeRunFn: async () => { throw new Error('browser-launch-failed'); } },
    );
  } finally {
    process.stdout.write = orig;
  }
  assert.strictEqual(code, EXIT.skipped);
  const output = JSON.parse(chunks.join(''));
  assert.ok('skip_reason' in output, 'skipped output must carry skip_reason field');
  assert.strictEqual(output.skip_reason, 'browser-launch-failed');
});

test('run_main violation with empty tags array does not gate', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:3000/'],
    { axeRunFn: async () => ({ violations: [{ id: 'x', tags: [], help: 'h', nodes: [] }], incomplete: [] }) },
  );
  assert.strictEqual(code, EXIT.ok, 'violation with empty tags must not gate (no GATING_TAG intersection)');
});
