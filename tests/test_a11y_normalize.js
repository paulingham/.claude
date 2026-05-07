// AC15 — normalize_mcp_yaml + normalize_library_json byte-equivalent for the
// same DOM. Uses node:test built-in runner; node 18+ exposes it natively.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const {
  normalize_mcp_yaml,
  normalize_library_json,
} = require(path.join(repoRoot, 'hooks', '_lib', 'a11y_normalize.js'));

test('normalize_mcp_yaml and normalize_library_json byte-equal for same DOM', () => {
  const fixturesDir = path.join(repoRoot, 'tests', 'fixtures', 'a11y', 'normalize');
  const yamlStr = fs.readFileSync(
    path.join(fixturesDir, 'mcp_payload.yaml'), 'utf8');
  const libRoot = JSON.parse(fs.readFileSync(
    path.join(fixturesDir, 'library_payload.json'), 'utf8'));

  const route = '/dashboard';
  const viewport = 'desktop';
  const capturedAt = '2026-05-07T11:30:00Z';

  const fromMcp = normalize_mcp_yaml(yamlStr, viewport, route, capturedAt);
  const fromLib = normalize_library_json(libRoot, viewport, route, capturedAt);

  // Adapter must zero out path-divergent fields (e.g., MCP `ref`) so the
  // byte serialization is identical regardless of capture path.
  const a = JSON.stringify(fromMcp, Object.keys(fromMcp).sort());
  const b = JSON.stringify(fromLib, Object.keys(fromLib).sort());
  assert.strictEqual(a, b, 'mcp and library normalised JSON must be byte-equal');
});

test('normalised snapshot has required top-level keys', () => {
  const fixturesDir = path.join(repoRoot, 'tests', 'fixtures', 'a11y', 'normalize');
  const libRoot = JSON.parse(fs.readFileSync(
    path.join(fixturesDir, 'library_payload.json'), 'utf8'));

  const out = normalize_library_json(libRoot, 'desktop', '/dashboard',
    '2026-05-07T11:30:00Z');

  for (const key of ['schema_version', 'route', 'viewport', 'captured_at',
                     'tree']) {
    assert.ok(key in out, `missing key ${key}`);
  }
  assert.strictEqual(out.schema_version, 1);
});

test('normalise tree node has required canonical fields', () => {
  const fixturesDir = path.join(repoRoot, 'tests', 'fixtures', 'a11y', 'normalize');
  const libRoot = JSON.parse(fs.readFileSync(
    path.join(fixturesDir, 'library_payload.json'), 'utf8'));

  const out = normalize_library_json(libRoot, 'desktop', '/dashboard',
    '2026-05-07T11:30:00Z');

  const tree = out.tree;
  for (const key of ['role', 'name', 'interactive', 'disabled', 'aria',
                     'ref', 'tag', 'children']) {
    assert.ok(key in tree, `missing tree key ${key}`);
  }
  for (const ariaKey of ['level', 'checked', 'expanded', 'pressed',
                         'selected', 'hidden']) {
    assert.ok(ariaKey in tree.aria, `missing aria.${ariaKey}`);
  }
});

test('normalize_mcp_yaml rejects non-string input', () => {
  assert.throws(
    () => normalize_mcp_yaml(null, 'desktop', '/x', '2026-05-07T00:00:00Z'),
    /string/i);
});

test('normalize_library_json rejects non-object input', () => {
  assert.throws(
    () => normalize_library_json(null, 'desktop', '/x', '2026-05-07T00:00:00Z'),
    /object/i);
});
