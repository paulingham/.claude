// Multi-route tests for axe_runner.js (per-route verdicts, exit code, empty tags).
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main, EXIT } = require(path.join(__dirname, '..', 'hooks', '_lib', 'axe_runner.js'));
const { makeCleanResult, makeWcag2aaResult, captureStdout } = require('./_helpers/axe_runner_stubs.js');

test('run_main multi-route: callCount===2, per-route verdicts correct', async () => {
  let callCount = 0;
  const output = await captureStdout(() => run_main(
    ['--url', 'http://localhost:3000/', '--url', 'http://localhost:3000/dashboard'],
    { axeRunFn: async (url) => { callCount++; return url.includes('/dashboard') ? makeWcag2aaResult() : makeCleanResult(); } },
  ));
  assert.strictEqual(callCount, 2, 'axeRunFn must be called once per route');
  assert.strictEqual(output.routes.length, 2);
  assert.strictEqual(output.routes[0].verdict, 'A11Y_CHECK_PASSED');
  assert.strictEqual(output.routes[1].verdict, 'A11Y_CHECK_FAILED');
});

test('run_main multi-route one bad route yields EXIT.failed exit code', async () => {
  const chunks = [];
  const orig = process.stdout.write.bind(process.stdout);
  process.stdout.write = chunk => { chunks.push(chunk); return true; };
  let code;
  try {
    code = await run_main(
      ['--url', 'http://localhost:3000/', '--url', 'http://localhost:3000/bad'],
      { axeRunFn: async (url) => url.includes('/bad') ? makeWcag2aaResult() : makeCleanResult() },
    );
  } finally {
    process.stdout.write = orig;
  }
  assert.strictEqual(code, EXIT.failed, 'multi-route with one bad route must return EXIT.failed');
});

test('run_main violation with empty tags array does not gate', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:3000/'],
    { axeRunFn: async () => ({ violations: [{ id: 'x', tags: [], help: 'h', nodes: [] }], incomplete: [] }) },
  );
  assert.strictEqual(code, EXIT.ok, 'violation with empty tags must not gate');
});
