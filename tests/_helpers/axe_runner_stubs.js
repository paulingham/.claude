// Shared stubs and helpers for axe_runner unit tests.
'use strict';

function makeCleanResult() {
  return { violations: [], incomplete: [] };
}

function makeWcag2aaResult() {
  return {
    violations: [{ id: 'color-contrast', tags: ['wcag2aa'], help: 'Fix contrast', nodes: [{ target: '.btn', html: '<button>' }] }],
    incomplete: [],
  };
}

// Capture stdout writes during an async fn, restore after.
async function captureStdout(fn) {
  const chunks = [];
  const orig = process.stdout.write.bind(process.stdout);
  process.stdout.write = chunk => { chunks.push(chunk); return true; };
  try {
    await fn();
  } finally {
    process.stdout.write = orig;
  }
  return JSON.parse(chunks.join(''));
}

// Save/restore CLAUDE_A11Y env var around a callback.
async function withA11yEnv(value, fn) {
  const saved = process.env.CLAUDE_A11Y;
  process.env.CLAUDE_A11Y = value;
  try {
    return await fn();
  } finally {
    if (saved === undefined) delete process.env.CLAUDE_A11Y;
    else process.env.CLAUDE_A11Y = saved;
  }
}

module.exports = { makeCleanResult, makeWcag2aaResult, captureStdout, withA11yEnv };
