// AC16 — probe_mcp_availability uses an injected invoker; tests cover
// success, timeout, and error paths without spawning real MCP.

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const { probe_mcp_availability } = require(
  path.join(repoRoot, 'hooks', '_lib', 'a11y_probe.js'));

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
