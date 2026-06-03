// Core route-scanning logic for axe_runner.js.
// Extracted to stay within 50-line shape limit.
'use strict';
function _is_gating(v, tags) { return v.tags.some(t => tags.includes(t)); }
function _map_gating(violations, url, tags) {
  return violations.filter(v => _is_gating(v, tags)).map(v => ({
    id: v.id, help: v.help,
    nodes: v.nodes.map(n => ({ target: n.target, html: n.html })),
    route_url: url,
  }));
}
async function _scan_routes(urls, deps, gatingTags) {
  const allGating = []; const allIncomplete = []; const routes = [];
  for (const url of urls) {
    let result;
    try { result = await deps.axeRunFn(url); }
    catch (_) { return { skipped: true, skipReason: 'browser-launch-failed', output: { routes } }; }
    const gating = _map_gating(result.violations, url, gatingTags);
    const routeVerdict = gating.length > 0 ? 'A11Y_CHECK_FAILED' : 'A11Y_CHECK_PASSED';
    allGating.push(...gating); allIncomplete.push(...result.incomplete);
    routes.push({ url, verdict: routeVerdict, gating_violations: gating, incomplete: result.incomplete });
  }
  const verdict = allGating.length > 0 ? 'A11Y_CHECK_FAILED' : 'A11Y_CHECK_PASSED';
  const output = {
    verdict, gating_violations: allGating, incomplete: allIncomplete, routes,
    violations: routes.flatMap(r => r.gating_violations),
  };
  return { skipped: false, verdict, output };
}
function _skipped_json(reason, routes) {
  return JSON.stringify({ verdict: 'A11Y_CHECK_SKIPPED', gating_violations: [], incomplete: [], routes, skip_reason: reason });
}
module.exports = { _scan_routes, _skipped_json };
