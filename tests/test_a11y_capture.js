// AC16 — probe_mcp_availability uses an injected invoker; tests cover
// success, timeout, and error paths without spawning real MCP.
//
// Capture entry coverage — run_main + write_snapshot exercised via stub
// mcp_capture / library_capture deps; on-disk snapshot is parsed back to
// confirm the `tree` field is populated (regression guard for the
// JSON.stringify replacer-as-allowlist bug that made every snapshot
// hollow).

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const { probe_mcp_availability } = require(
  path.join(repoRoot, 'hooks', '_lib', 'a11y_probe.js'));
const { run_main, EXIT } = require(
  path.join(repoRoot, 'hooks', '_lib', 'a11y_capture.js'));

test('probe_mcp_availability returns ok=true when invoker resolves', async () => {
  const okInvoker = async () => ({ ok: true });
  const result = await probe_mcp_availability(okInvoker, 2000);
  assert.strictEqual(result.ok, true);
});

test('probe_mcp_availability returns ok=false on invoker error', async () => {
  const badInvoker = async () => { throw new Error('mcp not connected'); };
  const result = await probe_mcp_availability(badInvoker, 2000);
  assert.strictEqual(result.ok, false);
  assert.match(result.reason, /not connected|error/i);
});

test('probe_mcp_availability times out at provided timeout_ms', async () => {
  const slowInvoker = () => new Promise(() => { /* never resolves */ });
  const start = Date.now();
  const result = await probe_mcp_availability(slowInvoker, 50);
  const elapsed = Date.now() - start;
  assert.strictEqual(result.ok, false);
  assert.match(result.reason, /timeout/i);
  // Generous upper bound; real timeout is ~50ms.
  assert.ok(elapsed < 1000, `expected fast timeout but elapsed=${elapsed}ms`);
});

test('probe_mcp_availability defaults timeout to 2000ms when omitted', async () => {
  const okInvoker = async () => ({ ok: true });
  const result = await probe_mcp_availability(okInvoker);
  assert.strictEqual(result.ok, true);
});

test('probe_mcp_availability requires a callable invoker', async () => {
  await assert.rejects(
    probe_mcp_availability(null, 1000),
    /function|callable|invoker/i);
});

function _mkOutPath() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'a11y-capture-'));
  return path.join(dir, 'snap.json');
}

test('run_main library path writes snapshot with non-empty tree', () => {
  const outPath = _mkOutPath();
  const libraryRoot = {
    role: 'WebArea',
    name: 'Dashboard',
    tag: 'html',
    children: [
      { role: 'button', name: 'Open menu', tag: 'button',
        interactive: true, children: [] },
    ],
  };
  const code = run_main(
    ['--route', '/dashboard', '--viewport', 'desktop',
     '--out', outPath, '--probe-result', 'library'],
    {
      now: () => '2026-05-07T11:30:00Z',
      library_capture: () => libraryRoot,
      mcp_capture: () => { throw new Error('should not be called'); },
    });
  assert.strictEqual(code, EXIT.ok);

  const snap = JSON.parse(fs.readFileSync(outPath, 'utf8'));
  assert.strictEqual(snap.schema_version, 1);
  assert.strictEqual(snap.route, '/dashboard');
  assert.strictEqual(snap.viewport, 'desktop');
  assert.ok(snap.tree, 'tree must be present');
  assert.strictEqual(snap.tree.role, 'WebArea');
  assert.ok(Array.isArray(snap.tree.children), 'tree.children must be an array');
  assert.strictEqual(snap.tree.children.length, 1,
    'tree.children must be populated by the library adapter');
  assert.strictEqual(snap.tree.children[0].role, 'button');
  assert.strictEqual(snap.tree.children[0].name, 'Open menu');
});

test('run_main mcp path writes snapshot with non-empty tree', () => {
  const outPath = _mkOutPath();
  const yamlPayload = [
    '- role: WebArea',
    '  name: Dashboard',
    '  tag: html',
    '  hidden: false',
    '  children:',
    '    - role: button',
    '      name: Open menu',
    '      tag: button',
    '      hidden: false',
    '      interactive: true',
    '      children: []',
    '',
  ].join('\n');
  const code = run_main(
    ['--route', '/dashboard', '--viewport', 'desktop',
     '--out', outPath, '--probe-result', 'mcp'],
    {
      now: () => '2026-05-07T11:30:00Z',
      mcp_capture: () => yamlPayload,
      library_capture: () => { throw new Error('should not be called'); },
    });
  assert.strictEqual(code, EXIT.ok);

  const snap = JSON.parse(fs.readFileSync(outPath, 'utf8'));
  assert.strictEqual(snap.tree.role, 'WebArea');
  assert.strictEqual(snap.tree.children.length, 1);
  assert.strictEqual(snap.tree.children[0].name, 'Open menu');
});

test('run_main returns capture_error when --route/--viewport/--out missing', () => {
  const code = run_main(['--route', '/x'], {});
  assert.strictEqual(code, EXIT.capture_error);
});
