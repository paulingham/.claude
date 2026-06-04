// Spec-blind helpers — authored from contract only, no build-agent stubs.
'use strict';
function cleanAxeResult() { return { violations: [], incomplete: [] }; }
function violationResult(tags) {
  return { violations: [{ id: 'spec-blind-v', tags, help: 'spec-blind help', nodes: [{ target: '.x', html: '<div>' }] }], incomplete: [] };
}
async function captureStdoutJSON(thunk) {
  const chunks = [];
  const origWrite = process.stdout.write.bind(process.stdout);
  process.stdout.write = chunk => { chunks.push(String(chunk)); return true; };
  try { await thunk(); } finally { process.stdout.write = origWrite; }
  return JSON.parse(chunks.join(''));
}
async function withEnvVar(name, value, thunk) {
  const saved = process.env[name];
  process.env[name] = value;
  try { return await thunk(); } finally {
    if (saved === undefined) delete process.env[name]; else process.env[name] = saved;
  }
}
module.exports = { cleanAxeResult, violationResult, captureStdoutJSON, withEnvVar };
