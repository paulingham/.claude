"""Multi-target E2E resolver for `/verify` Tier 4.

Computes per-target firing status (`mobile`, `web`) from a changed-files list
plus project-root inspection (maestro/, playwright.config.*, cypress.config.*).
Applies the M5 strict flake gate (`> 0.05`) and composes per-target results
into the Tier 4 composite verdict.

Glob-matching mitigations (H1):
- Brace expansion: `**/sw.{js,ts}` → `["**/sw.js", "**/sw.ts"]`
- Top-level fallback: `**/middleware.ts` also matches bare `middleware.ts`

Both empirically failed under bare `fnmatch` for the canonical patterns;
both are locked by AC30 + AC31.
"""
from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path

# ---------------- Tier 0 constants (locked by AC12, AC13, AC25, AC26, AC28) ----------------

SCREENSHOT_PATH_TEMPLATE = (
    "pipeline-state/{task_id}/scratchpad/qa-engineer-verify-screenshots/")

WEB_FLAKE_THRESHOLD = 0.05  # strict `>`; AC15 + AC26 lock the boundary.

PER_TARGET_STATUS_ENUM = frozenset({"PASS", "FAIL", "SKIP", "N/A"})

# ---------------- Glob patterns (canonical schema, S1 §2) ----------------

MOBILE_PATTERNS = (
    "**/url-classification.ts", "**/url-parse-helpers.ts",
    "**/navigation-helpers.ts", "**/useNavigationHandler.ts",
    "**/navigationCallbacks.ts",
    "**/session-store.ts", "**/session-message-handler.ts",
    "**/useWebViewAuth.ts", "**/useWebViewMessages.ts",
    "**/useBiometricGating.ts", "**/useBiometricState.ts",
    "**/biometric-auth.ts",
    "**/WebViewContainer.tsx", "**/WebViewScreen.tsx",
    "**/_layout.tsx", "**/index.tsx",
    "**/NetworkBanner.tsx", "**/useNetworkStatus.ts",
    "**/file-download.ts", "**/cookie-manager.ts",
    "**/viewport-meta.ts", "**/session-check.ts",
    "**/css-forms-buttons.ts", "**/css-containers.ts",
    "**/css-base-layout.ts", "**/css-media-elements.ts",
    "**/css-document-viewer.ts", "**/css-assembly.ts",
)

WEB_PATTERNS = (
    # auth-flow
    "**/*Auth*.{tsx,ts,jsx,js}", "**/login/**", "**/logout/**",
    "**/session/**", "**/middleware.ts",
    # routing-redirect
    "**/middleware.{js,ts}", "**/_redirects",
    "**/next.config.{js,ts,mjs}", "**/router/**",
    # form-submission
    "**/*Form*.{tsx,ts,jsx,js}", "**/forms/**", "**/actions/**",
    "**/api/**/*.{ts,js}",
    # payment-checkout
    "**/checkout/**", "**/payment*/**", "**/billing/**",
    "**/stripe/**", "**/*Checkout*.{tsx,ts}",
    # third-party-iframe
    "**/*Iframe*.{tsx,ts}", "**/embed*/**", "**/widgets/**",
    # service-worker
    "**/sw.{js,ts}", "**/service-worker.{js,ts}",
    "**/workbox*.{js,ts}",
)


# ---------------- Glob mitigations (H1 — AC30, AC31) ----------------


def _expand_braces(pattern):
    """Expand a single `{a,b,c}` group to a list of patterns.

    `**/sw.{js,ts}` → `["**/sw.js", "**/sw.ts"]`. Patterns without a brace
    pass through as `[pattern]`. Only one group is supported per pattern
    (the canonical schema needs no more); multiple groups would require
    a Cartesian expansion, intentionally out of scope.
    """
    match = re.search(r"\{([^{}]+)\}", pattern)
    if not match:
        return [pattern]
    options = [opt.strip() for opt in match.group(1).split(",")]
    return [pattern[:match.start()] + opt + pattern[match.end():]
            for opt in options]


def _matches_any(file, patterns):
    """True iff `file` matches any pattern after brace + top-level mitigations."""
    for pat in patterns:
        for expanded in _expand_braces(pat):
            if fnmatch(file, expanded):
                return True
            if expanded.startswith("**/") and fnmatch(file, expanded[3:]):
                return True
    return False


# ---------------- Project inspection (small, single-purpose helpers) ----------------


def _has_maestro_dir(project_root):
    return (Path(project_root) / "maestro").is_dir()


def _has_playwright_config(project_root):
    root = Path(project_root)
    return (root / "playwright.config.ts").exists() \
        or (root / "playwright.config.js").exists()


def _has_cypress_config(project_root):
    root = Path(project_root)
    return (root / "cypress.config.ts").exists() \
        or (root / "cypress.config.js").exists()


# ---------------- Per-target matchers (independent — AC9, AC27) ----------------


def _match_mobile(changed_files):
    return any(_matches_any(f, MOBILE_PATTERNS) for f in changed_files)


def _match_web(changed_files):
    return any(_matches_any(f, WEB_PATTERNS) for f in changed_files)


# ---------------- Public API ----------------


def detect_targets(changed_files, project_root):
    """Per-target firing status — `{"mobile": status, "web": status}`.

    Status values are the AC schema: `"FIRED"` when a glob matches AND
    the project has the requisite environment (maestro/ for mobile,
    playwright/cypress config for web). `"N/A"` otherwise.

    Both matchers run independently (no short-circuit) so a diff that
    spans both targets fires both.
    """
    mobile = "FIRED" if _match_mobile(changed_files) \
        and _has_maestro_dir(project_root) else "N/A"
    has_web_config = (_has_playwright_config(project_root)
                      or _has_cypress_config(project_root))
    web = "FIRED" if _match_web(changed_files) and has_web_config else "N/A"
    return {"mobile": mobile, "web": web}


def select_web_driver(project_root):
    """Resolve the web driver (M4: prefer Playwright when both configs present).

    Returns `{"driver": "playwright"|"cypress"|None, "warning": str|None}`.
    Warning is set only when both configs are present (one-line emit hint
    for the verify report).
    """
    has_pw = _has_playwright_config(project_root)
    has_cy = _has_cypress_config(project_root)
    if has_pw and has_cy:
        return {
            "driver": "playwright",
            "warning": ("Both playwright and cypress configs detected; "
                        "defaulting to playwright. Remove one config to "
                        "silence this warning."),
        }
    if has_pw:
        return {"driver": "playwright", "warning": None}
    if has_cy:
        return {"driver": "cypress", "warning": None}
    return {"driver": None, "warning": None}


def coerce_web_status_for_flake(target_results, flake_rate):
    """Strict-`>` flake gate (M5): web → FAIL when `flake_rate > 0.05`.

    Idempotent. Returns a copy; does not mutate input.
    """
    coerced = dict(target_results)
    if "web" in coerced and flake_rate > WEB_FLAKE_THRESHOLD:
        coerced["web"] = "FAIL"
    return coerced


def compose_verdict(target_results):
    """Compose per-target results into the Tier 4 verdict.

    Inputs MUST come from `PER_TARGET_STATUS_ENUM` (`PASS|FAIL|SKIP|N/A`)
    OR be the unfired sentinel `"N/A"`. The pipeline also passes a
    bridge value `"FIRED"` from `detect_targets` for not-yet-executed
    targets — `compose_verdict` is called AFTER the suite runs and must
    receive PASS/FAIL/SKIP/N/A only. Invalid values raise ValueError.
    """
    valid = PER_TARGET_STATUS_ENUM
    statuses = list(target_results.values())
    bad = [s for s in statuses if s not in valid]
    if bad:
        raise ValueError(
            f"Invalid per-target status(es) {bad!r}; "
            f"must be in {sorted(valid)}")
    if any(s == "FAIL" for s in statuses):
        return "UNVERIFIED"
    if any(s == "SKIP" for s in statuses):
        return "VERIFIED_WITH_SKIP"
    return "VERIFIED"
