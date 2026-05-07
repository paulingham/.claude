// MCP availability probe — DI-friendly. Production binds `invoker` to
// the active MCP client's send method; tests inject stubs.

'use strict';

const DEFAULT_TIMEOUT_MS = 2000;

async function probe_mcp_availability(invoker, timeout_ms) {
  if (typeof invoker !== 'function') {
    throw new TypeError('probe_mcp_availability: invoker must be a function');
  }
  const ms = Number.isFinite(timeout_ms) ? timeout_ms : DEFAULT_TIMEOUT_MS;
  try {
    return await _race(invoker, ms);
  } catch (err) {
    return { ok: false, reason: err && err.message ? err.message : 'error' };
  }
}

async function _race(invoker, ms) {
  let timer;
  try {
    return await Promise.race([
      Promise.resolve().then(() => invoker()).then(_normaliseResult),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('timeout')), ms);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function _normaliseResult(result) {
  if (result && typeof result === 'object' && 'ok' in result) {
    return result;
  }
  return { ok: true };
}

module.exports = {
  probe_mcp_availability,
  DEFAULT_TIMEOUT_MS,
};
