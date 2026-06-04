// axe-core runner — scans URLs for WCAG 2.1 A/AA violations.
// DI: deps.axeRunFn(url) => Promise<{violations[], incomplete[]}>
// Exit: 0=ok, 1=failed, 2=skipped.
'use strict';
const path = require('node:path');
const fs = require('node:fs');
const { _scan_routes, _skipped_json } = require('./axe_runner_core.js');
const { _resolve_cli_deps, _make_axe_run_fn } = require('./axe_runner_cli.js');
const EXIT = { ok: 0, failed: 1, skipped: 2 };
const GATING_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

function _parse_urls(argv) {
  const urls = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--url') urls.push(argv[++i]);
  }
  return urls;
}

async function run_main(argv, deps) {
  if (process.env.CLAUDE_A11Y === '0') {
    process.stdout.write(_skipped_json('env-hatch', []));
    return EXIT.skipped;
  }
  const urls = _parse_urls(argv);
  if (urls.length === 0) throw new Error('axe_runner: at least one --url flag is required');
  const { verdict, output, skipped, skipReason } = await _scan_routes(urls, deps, GATING_TAGS);
  if (skipped) {
    process.stdout.write(_skipped_json(skipReason, output.routes));
    return EXIT.skipped;
  }
  process.stdout.write(JSON.stringify(output));
  return verdict === 'A11Y_CHECK_FAILED' ? EXIT.failed : EXIT.ok;
}

if (require.main === module) {
  const candidates = [
    process.cwd(),
    path.join(__dirname, '..', '..', 'tests', 'fixtures', 'accessibility-check', '.deps'),
  ];
  const resolved = _resolve_cli_deps(candidates, require, fs.readFileSync.bind(fs));
  if (!resolved) {
    process.stderr.write('axe_runner: playwright/axe-core not found — emitting SKIPPED\n');
    process.stdout.write(_skipped_json('browser-launch-failed', []));
    process.exit(EXIT.skipped);
  }
  const onErr = e => { process.stderr.write(`axe_runner: ${e.message}\n`); process.exit(EXIT.failed); };
  run_main(process.argv.slice(2), { axeRunFn: _make_axe_run_fn(resolved.chromium, resolved.axeSource) }).then(c => process.exit(c)).catch(onErr);
}
module.exports = { run_main, EXIT, GATING_TAGS, _resolve_cli_deps, _make_axe_run_fn };
