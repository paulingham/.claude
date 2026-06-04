// Skip-path + route_url output shape tests for axe_runner.js.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { run_main, EXIT } = require(path.join(__dirname, '..', 'hooks', '_lib', 'axe_runner.js'));
const { makeWcag2aaResult, captureStdout } = require('./_helpers/axe_runner_stubs.js');

test('run_main gating_violations items carry route_url field', async () => {
  const output = await captureStdout(() => run_main(
    ['--url', 'http://localhost:3000/page'],
    { axeRunFn: async () => makeWcag2aaResult() },
  ));
  assert.ok(output.gating_violations.length > 0, 'must have gating_violations');
  assert.strictEqual(output.gating_violations[0].route_url, 'http://localhost:3000/page');
});

test('run_main skipped output has skip_reason and gating_violations array', async () => {
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
  assert.ok(Array.isArray(output.gating_violations), 'SKIPPED output must have gating_violations array (M3)');
});
