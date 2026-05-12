// Playwright driver for the Tier 2 integration test.
//
// Mirrors the SKILL.md Step 6 pump shape: chromium.launch + page.goto +
// screenshot, written to the configured snapshot output dir
// (env $PW_OUTPUT_DIR) — equivalent to the testConfig.snapshotDir override
// documented in skills/design-qc/SKILL.md (failure-mode-9 / SE-5).
//
// Inputs (env):
//   PW_OUTPUT_DIR   absolute path the driver writes PNGs into.
//   PW_SLUG         route slug (e.g. "home") — becomes filename prefix.
//   PW_PORT         port the fixture server listens on.

'use strict';

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('@playwright/test');

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 375, height: 812 },
];

async function waitForServer(port, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      await fetch(`http://127.0.0.1:${port}/`);
      return;
    } catch (_) {
      await new Promise((r) => setTimeout(r, 200));
    }
  }
  throw new Error(`fixture server did not start within ${timeoutMs}ms`);
}

async function main() {
  const outDir = process.env.PW_OUTPUT_DIR;
  const slug = process.env.PW_SLUG || 'home';
  const port = parseInt(process.env.PW_PORT || '4321', 10);

  if (!outDir) {
    throw new Error('PW_OUTPUT_DIR required');
  }
  fs.mkdirSync(outDir, { recursive: true });

  // Start the fixture server in-process.
  const serverPath = path.join(__dirname, 'server.js');
  const server = spawn(process.execPath, [serverPath], {
    env: { ...process.env, PORT: String(port) },
    stdio: 'ignore',
  });

  try {
    await waitForServer(port, 5000);
    const browser = await chromium.launch({ headless: true });
    try {
      for (const viewport of VIEWPORTS) {
        const ctx = await browser.newContext({
          viewport: { width: viewport.width, height: viewport.height },
        });
        const page = await ctx.newPage();
        await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'networkidle' });
        const outPath = path.join(outDir, `${slug}-${viewport.name}.png`);
        await page.screenshot({ path: outPath, fullPage: false });
        await ctx.close();
      }
    } finally {
      await browser.close();
    }
  } finally {
    server.kill('SIGTERM');
  }
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
