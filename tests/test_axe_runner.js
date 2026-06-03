// Unit tests for hooks/_lib/axe_runner.js
// Uses node:test + node:assert/strict; DI-stubbed axeRunFn; no real browser.
// Mirrors the pattern from tests/test_a11y_capture.js.

'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const { run_main, EXIT } = require(
  path.join(repoRoot, 'hooks', '_lib', 'axe_runner.js'));

// --- Helper stubs ---

function makeCleanResult() {
  return { violations: [], incomplete: [] };
}

function makeWcag2aaResult() {
  return {
    violations: [{ id: 'color-contrast', tags: ['wcag2aa'], help: 'Fix contrast', nodes: [{ target: '.btn', html: '<button>' }] }],
    incomplete: [],
  };
}

// Restore env-var saved before each env-mutation test.
let savedA11y;

test('run_main exports and EXIT codes present', () => {
  assert.strictEqual(typeof run_main, 'function');
  assert.strictEqual(EXIT.ok, 0);
  assert.strictEqual(EXIT.failed, 1);
  assert.strictEqual(EXIT.skipped, 2);
});

test('run_main with wcag2aa stub violation returns EXIT.failed', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:3000/'],
    { axeRunFn: async () => makeWcag2aaResult() },
  );
  assert.strictEqual(code, EXIT.failed);
});

test('run_main with zero violations returns EXIT.ok', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:3000/'],
    { axeRunFn: async () => makeCleanResult() },
  );
  assert.strictEqual(code, EXIT.ok);
});

test('run_main gates on wcag2a tagged violation', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:3000/'],
    {
      axeRunFn: async () => ({
        violations: [{ id: 'image-alt', tags: ['wcag2a'], help: 'Add alt text', nodes: [{ target: 'img', html: '<img>' }] }],
        incomplete: [],
      }),
    },
  );
  assert.strictEqual(code, EXIT.failed);
});

test('run_main gates on wcag21aa tagged violation', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:3000/'],
    {
      axeRunFn: async () => ({
        violations: [{ id: 'focus-visible', tags: ['wcag21aa'], help: 'Focus visible', nodes: [{ target: 'a', html: '<a>' }] }],
        incomplete: [],
      }),
    },
  );
  assert.strictEqual(code, EXIT.failed);
});

test('run_main gates on wcag21a tagged violation', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:3000/'],
    {
      axeRunFn: async () => ({
        violations: [{ id: 'label', tags: ['wcag21a'], help: 'Label', nodes: [{ target: 'input', html: '<input>' }] }],
        incomplete: [],
      }),
    },
  );
  assert.strictEqual(code, EXIT.failed);
});

test('run_main with best-practice-only violation returns EXIT.ok', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:3000/'],
    {
      axeRunFn: async () => ({
        violations: [{ id: 'skip-link', tags: ['best-practice'], help: 'Add skip link', nodes: [{ target: 'body', html: '<body>' }] }],
        incomplete: [],
      }),
    },
  );
  assert.strictEqual(code, EXIT.ok);
});

test('run_main with only incomplete results returns EXIT.ok', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:3000/'],
    {
      axeRunFn: async () => ({
        violations: [],
        incomplete: [{ id: 'color-contrast', tags: ['wcag2aa'], help: 'Needs review', nodes: [] }],
      }),
    },
  );
  assert.strictEqual(code, EXIT.ok);
});

test('run_main with CLAUDE_A11Y=0 returns EXIT.skipped', async () => {
  savedA11y = process.env.CLAUDE_A11Y;
  process.env.CLAUDE_A11Y = '0';
  try {
    const code = await run_main(
      ['--url', 'http://localhost:3000/'],
      { axeRunFn: async () => makeWcag2aaResult() },
    );
    assert.strictEqual(code, EXIT.skipped);
  } finally {
    if (savedA11y === undefined) {
      delete process.env.CLAUDE_A11Y;
    } else {
      process.env.CLAUDE_A11Y = savedA11y;
    }
  }
});

test('run_main with axeRunFn throwing returns EXIT.skipped', async () => {
  const code = await run_main(
    ['--url', 'http://localhost:3000/'],
    {
      axeRunFn: async () => { throw new Error('browser-launch-failed'); },
    },
  );
  assert.strictEqual(code, EXIT.skipped);
});

test('run_main output JSON shape is correct', async () => {
  const chunks = [];
  const origWrite = process.stdout.write.bind(process.stdout);
  process.stdout.write = (chunk) => { chunks.push(chunk); return true; };
  try {
    await run_main(
      ['--url', 'http://localhost:3000/'],
      { axeRunFn: async () => makeCleanResult() },
    );
  } finally {
    process.stdout.write = origWrite;
  }
  const output = JSON.parse(chunks.join(''));
  assert.ok('verdict' in output, 'output must have verdict field');
  assert.ok(Array.isArray(output.violations), 'output must have violations array');
  assert.ok(Array.isArray(output.incomplete), 'output must have incomplete array');
  assert.ok(Array.isArray(output.gating_violations), 'output must have gating_violations array');
  assert.ok(Array.isArray(output.routes), 'output must have routes array');
});

test('run_main gating_violations items have actionability fields', async () => {
  const chunks = [];
  const origWrite = process.stdout.write.bind(process.stdout);
  process.stdout.write = (chunk) => { chunks.push(chunk); return true; };
  try {
    await run_main(
      ['--url', 'http://localhost:3000/'],
      {
        axeRunFn: async () => ({
          violations: [{ id: 'color-contrast', tags: ['wcag2aa'], help: 'Fix contrast', nodes: [{ target: '.btn', html: '<button>' }] }],
          incomplete: [],
        }),
      },
    );
  } finally {
    process.stdout.write = origWrite;
  }
  const output = JSON.parse(chunks.join(''));
  assert.ok(output.gating_violations.length > 0, 'gating_violations must be non-empty');
  const gv = output.gating_violations[0];
  assert.ok('id' in gv, 'gating_violation must have id');
  assert.ok('help' in gv, 'gating_violation must have help');
  assert.ok(Array.isArray(gv.nodes), 'gating_violation must have nodes array');
  assert.ok('target' in gv.nodes[0], 'node must have target');
  assert.ok('html' in gv.nodes[0], 'node must have html');
});

test('run_main multi-route one bad route yields EXIT.failed', async () => {
  let callCount = 0;
  const chunks = [];
  const origWrite = process.stdout.write.bind(process.stdout);
  process.stdout.write = (chunk) => { chunks.push(chunk); return true; };
  try {
    const code = await run_main(
      ['--url', 'http://localhost:3000/', '--url', 'http://localhost:3000/dashboard'],
      {
        axeRunFn: async (url) => {
          callCount++;
          if (url.includes('/dashboard')) {
            return makeWcag2aaResult();
          }
          return makeCleanResult();
        },
      },
    );
    assert.strictEqual(code, EXIT.failed);
  } finally {
    process.stdout.write = origWrite;
  }
  const output = JSON.parse(chunks.join(''));
  assert.strictEqual(output.routes.length, 2, 'both routes must be present in routes[]');
});

test('run_main always includes root route', async () => {
  const chunks = [];
  const origWrite = process.stdout.write.bind(process.stdout);
  process.stdout.write = (chunk) => { chunks.push(chunk); return true; };
  try {
    const code = await run_main(
      ['--url', '/'],
      { axeRunFn: async () => makeCleanResult() },
    );
    assert.strictEqual(code, EXIT.ok);
  } finally {
    process.stdout.write = origWrite;
  }
  const output = JSON.parse(chunks.join(''));
  assert.strictEqual(output.routes.length, 1);
  assert.strictEqual(output.routes[0].url, '/');
});
