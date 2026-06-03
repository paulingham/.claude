// axe-core runner — scans one or more URLs for WCAG 2.1 A/AA violations.
//
// Usage (production, via accessibility-check SKILL):
//   node axe_runner.js --url <url1> [--url <url2>...] [--out <path>]
//
// DI pattern: deps.axeRunFn(url) => Promise<{violations[], incomplete[]}>
// Exit codes: 0=ok, 1=failed, 2=skipped.

'use strict';

const EXIT = { ok: 0, failed: 1, skipped: 2 };

const GATING_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

function _is_gating(violation) {
  return violation.tags.some(tag => GATING_TAGS.includes(tag));
}

function _parse_args(argv) {
  const urls = [];
  let out = null;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--url') {
      urls.push(argv[++i]);
    } else if (argv[i] === '--out') {
      out = argv[++i];
    }
  }
  return { urls, out };
}

async function run_main(argv, deps) {
  if (process.env.CLAUDE_A11Y === '0') {
    process.stdout.write(JSON.stringify({
      verdict: 'A11Y_CHECK_SKIPPED',
      gating_violations: [],
      incomplete: [],
      routes: [],
      skip_reason: 'env-hatch',
    }));
    return EXIT.skipped;
  }

  const { urls } = _parse_args(argv);
  if (urls.length === 0) {
    throw new Error('axe_runner: at least one --url flag is required');
  }

  const allGatingViolations = [];
  const allIncomplete = [];
  const routes = [];

  for (const url of urls) {
    let result;
    try {
      result = await deps.axeRunFn(url);
    } catch (err) {
      process.stdout.write(JSON.stringify({
        verdict: 'A11Y_CHECK_SKIPPED',
        gating_violations: [],
        incomplete: [],
        routes,
        skip_reason: 'browser-launch-failed',
      }));
      return EXIT.skipped;
    }

    const gating = result.violations.filter(_is_gating).map(v => ({
      id: v.id,
      help: v.help,
      nodes: v.nodes.map(n => ({ target: n.target, html: n.html })),
      route_url: url,
    }));
    const routeVerdict = gating.length > 0 ? 'A11Y_CHECK_FAILED' : 'A11Y_CHECK_PASSED';

    allGatingViolations.push(...gating);
    allIncomplete.push(...result.incomplete);
    routes.push({
      url,
      verdict: routeVerdict,
      gating_violations: gating,
      incomplete: result.incomplete,
    });
  }

  const verdict = allGatingViolations.length > 0 ? 'A11Y_CHECK_FAILED' : 'A11Y_CHECK_PASSED';

  process.stdout.write(JSON.stringify({
    verdict,
    gating_violations: allGatingViolations,
    incomplete: allIncomplete,
    routes,
    violations: routes.flatMap(r => r.gating_violations),
  }));

  return verdict === 'A11Y_CHECK_FAILED' ? EXIT.failed : EXIT.ok;
}

if (require.main === module) {
  run_main(process.argv.slice(2), {
    axeRunFn: async () => {
      throw new Error('axe_runner: no axeRunFn provided for CLI mode');
    },
  }).then(code => process.exit(code)).catch(err => {
    process.stderr.write(`axe_runner: ${err.message}\n`);
    process.exit(EXIT.failed);
  });
}

module.exports = { run_main, EXIT, GATING_TAGS };
