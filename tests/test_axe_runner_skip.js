// CLI resolver DI tests for axe_runner.js (finding 1: _resolve_cli_deps).
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { _resolve_cli_deps } = require(path.join(__dirname, '..', 'hooks', '_lib', 'axe_runner.js'));

// Stub requireFn that succeeds for a known path prefix.
function makeRequireFn(knownBase) {
  return function requireFn(p) {
    if (p.startsWith(knownBase)) return { chromium: { launch: () => {} } };
    throw new Error(`not found: ${p}`);
  };
}

// Stub readFileFn that returns a fake axe source for known axe path.
function makeReadFileFn(knownBase) {
  return function readFileFn(p) {
    if (p.startsWith(knownBase) && p.endsWith('axe.min.js')) return '// axe stub';
    throw new Error(`not found: ${p}`);
  };
}

test('_resolve_cli_deps returns null when no candidate resolves', () => {
  const result = _resolve_cli_deps(
    ['/nonexistent/path/a', '/nonexistent/path/b'],
    () => { throw new Error('not found'); },
    () => { throw new Error('not found'); },
  );
  assert.strictEqual(result, null);
});

test('_resolve_cli_deps returns chromium+axeSource when first candidate resolves', () => {
  const base = '/fake/project';
  const result = _resolve_cli_deps(
    [base, '/other'],
    makeRequireFn(base),
    makeReadFileFn(base),
  );
  assert.ok(result !== null, 'should resolve from first candidate');
  assert.ok('chromium' in result, 'result must have chromium');
  assert.ok(typeof result.axeSource === 'string', 'result must have axeSource');
});

test('_resolve_cli_deps falls through to second candidate when first fails', () => {
  const base = '/fake/project';
  const result = _resolve_cli_deps(
    ['/will-fail', base],
    makeRequireFn(base),
    makeReadFileFn(base),
  );
  assert.ok(result !== null, 'should resolve from second candidate');
});
