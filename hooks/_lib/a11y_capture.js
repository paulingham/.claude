// Capture entry — wires probe + capture-path resolver + normaliser, and
// writes a per-snapshot JSON file at the path provided in `--out`.
//
// Usage (production, via design-qc § 6.25):
//   node a11y_capture.js --route /dashboard --viewport desktop \
//        --out pipeline-state/{task}/design-qc/a11y/dashboard-desktop.json
//
// Capture is invoked once per (route, viewport). The MCP probe runs
// once per design-qc invocation; this script accepts a `--probe-result`
// flag (`mcp` or `library`) so the parent can avoid re-probing.
//
// Exit codes: 0=ok, 1=mcp-unavailable, 2=capture-error, 3=schema-violation.

'use strict';

const fs = require('node:fs');
const path = require('node:path');
const {
  normalize_library_json,
  normalize_mcp_yaml,
} = require('./a11y_normalize.js');

const EXIT = {
  ok: 0,
  mcp_unavailable: 1,
  capture_error: 2,
  schema_violation: 3,
};

function parse_args(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const flag = argv[i];
    if (flag === '--route') out.route = argv[++i];
    else if (flag === '--viewport') out.viewport = argv[++i];
    else if (flag === '--out') out.out = argv[++i];
    else if (flag === '--probe-result') out.probe = argv[++i];
    else if (flag === '--source') out.source = argv[++i];
  }
  return out;
}

function write_snapshot(out_path, normalised) {
  fs.mkdirSync(path.dirname(out_path), { recursive: true });
  fs.writeFileSync(out_path, JSON.stringify(normalised, Object.keys(
    normalised).sort()));
}

function run_main(argv, deps) {
  const args = parse_args(argv);
  if (!args.route || !args.viewport || !args.out) {
    process.stderr.write('a11y_capture: missing --route / --viewport / --out\n');
    return EXIT.capture_error;
  }
  const captured_at = (deps && deps.now) ? deps.now()
    : new Date().toISOString();
  try {
    const normalised = _capture(args, deps, captured_at);
    write_snapshot(args.out, normalised);
    return EXIT.ok;
  } catch (err) {
    process.stderr.write(`a11y_capture: ${err.message}\n`);
    return _exit_for_error(err);
  }
}

function _capture(args, deps, captured_at) {
  const provider = (args.probe === 'mcp') ? 'mcp' : 'library';
  if (provider === 'mcp') {
    const yamlStr = (deps && deps.mcp_capture)
      ? deps.mcp_capture(args.route, args.viewport)
      : '';
    return normalize_mcp_yaml(yamlStr, args.viewport, args.route, captured_at);
  }
  const node = (deps && deps.library_capture)
    ? deps.library_capture(args.route, args.viewport)
    : { role: 'WebArea', children: [] };
  return normalize_library_json(node, args.viewport, args.route, captured_at);
}

function _exit_for_error(err) {
  const msg = (err && err.message) || '';
  if (/schema/i.test(msg)) return EXIT.schema_violation;
  if (/mcp[- ]unavailable/i.test(msg)) return EXIT.mcp_unavailable;
  return EXIT.capture_error;
}

if (require.main === module) {
  const code = run_main(process.argv.slice(2));
  process.exit(code);
}

module.exports = { run_main, parse_args, EXIT, write_snapshot };
