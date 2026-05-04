"""C3 — e2e-protocol.md multi-target structural assertions (AC1-AC6).

These tests lock the post-restructure shape of `rules/_detail/e2e-protocol.md`.
The mobile pre/post row-pair check (AC5) implements the M3 set-equality rule:
the post-restructure mobile matrix MUST be a superset of the pre-restructure
mobile matrix. Pre-restructure rows are pinned at the top of this file.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = REPO_ROOT / "rules" / "_detail" / "e2e-protocol.md"

# M3: Pre-restructure mobile (Category, Files) row pairs frozen here.
# Source: rules/_detail/e2e-protocol.md @ HEAD before this slice (lines 18-28).
PRE_MOBILE_ROW_PAIRS = frozenset({
    ("URL/Navigation",
     "`url-classification.ts`, `url-parse-helpers.ts`, "
     "`navigation-helpers.ts`, `useNavigationHandler.ts`, "
     "`navigationCallbacks.ts`"),
    ("Auth/Session",
     "`session-store.ts`, `session-message-handler.ts`, "
     "`useWebViewAuth.ts`, `useWebViewMessages.ts`"),
    ("Biometric",
     "`useBiometricGating.ts`, `useBiometricState.ts`, "
     "`biometric-auth.ts`"),
    ("WebView Core",
     "`WebViewContainer.tsx`, `WebViewScreen.tsx`, `_layout.tsx`, "
     "`index.tsx`"),
    ("Network", "`NetworkBanner.tsx`, `useNetworkStatus.ts`"),
    ("Downloads/Cookies", "`file-download.ts`, `cookie-manager.ts`"),
    ("Injection (behavioral)", "`viewport-meta.ts`, `session-check.ts`"),
    ("Constants (domain)",
     "`constants.ts` (only when `WEBVIEW_ORIGIN_WHITELIST` or "
     "domain URLs change)"),
    ("CSS Injection (layout)",
     "`css-forms-buttons.ts`, `css-containers.ts`, `css-base-layout.ts`, "
     "`css-media-elements.ts`, `css-document-viewer.ts`, "
     "`css-assembly.ts`"),
})

WEB_CATEGORIES = (
    "auth-flow",
    "routing-redirect",
    "form-submission",
    "payment-checkout",
    "third-party-iframe",
    "service-worker",
)


def _read():
    return PROTOCOL.read_text()


def _section_body(text, heading_marker, heading_text):
    """Return text from a heading until the next same-or-higher-level heading."""
    pattern = (re.escape(heading_marker) + r"\s+" +
               re.escape(heading_text) + r"\s*\n")
    match = re.search(pattern, text)
    if not match:
        return ""
    start = match.end()
    # Stop at any heading at the same or higher level.
    level = len(heading_marker)
    next_pattern = r"\n#{1," + str(level) + r"}\s+"
    rest = text[start:]
    next_match = re.search(next_pattern, rest)
    return rest[:next_match.start()] if next_match else rest


def _mobile_row_pairs_in(body):
    """Extract (Category, Files) tuples from a Markdown table body.

    Skips header (|---|...|) and any row whose first cell is empty.
    """
    pairs = set()
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") \
                or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0] in ("Category", ""):
            continue
        pairs.add((cells[0], cells[1]))
    return frozenset(pairs)


def test_top_level_targets_section_exists():
    """AC1: protocol has a `## Targets` H2 heading."""
    assert re.search(r"^##\s+Targets\b", _read(), re.MULTILINE), \
        "Expected `## Targets` H2 heading in e2e-protocol.md"


def test_mobile_and_web_subsections_exist():
    """AC2: `### Mobile (Maestro)` and `### Web (Playwright / Cypress)` H3 under Targets."""
    text = _read()
    targets_body = _section_body(text, "##", "Targets")
    assert re.search(r"^###\s+Mobile\s+\(Maestro\)\s*$",
                     targets_body, re.MULTILINE), \
        "Expected `### Mobile (Maestro)` under `## Targets`"
    assert re.search(r"^###\s+Web\s+\(Playwright\s*/\s*Cypress\)\s*$",
                     targets_body, re.MULTILINE), \
        "Expected `### Web (Playwright / Cypress)` under `## Targets`"


def test_web_six_canonical_categories_present():
    """AC3: all 6 canonical web categories present, each with example glob."""
    text = _read()
    for category in WEB_CATEGORIES:
        assert category in text, \
            f"Web category token '{category}' missing from e2e-protocol.md"
        # Each category MUST have at least one example glob (`**/...`)
        # within ~5 lines after the token. Use a bounded look-ahead.
        idx = text.find(category)
        window = text[idx:idx + 800]
        assert "**/" in window, \
            f"No example glob found near web category '{category}'"


def test_supplementary_backend_triggers_preserved():
    """AC4: Migrations + Public API contract reachable as supplementary back-end triggers."""
    text = _read()
    # Both must appear under the Web section as supplementary.
    targets_body = _section_body(text, "##", "Targets")
    web_body = _section_body(targets_body, "###",
                             "Web (Playwright / Cypress)")
    assert "Migrations" in web_body, \
        "Supplementary back-end trigger 'Migrations' missing from `### Web`"
    assert "Public API contract" in web_body, \
        "Supplementary back-end trigger 'Public API contract' missing"
    # Must indicate they are supplementary/back-end (not primary categories).
    assert re.search(r"[Ss]upplementary|[Bb]ack[- ]?end", web_body), \
        "Migrations + Public API contract not flagged as supplementary"


def test_mobile_trigger_matrix_row_pairs_preserved_as_superset():
    """AC5 (M3): post-restructure mobile (Category, Files) ⊇ pre-restructure."""
    text = _read()
    targets_body = _section_body(text, "##", "Targets")
    mobile_body = _section_body(targets_body, "###", "Mobile (Maestro)")
    post_pairs = _mobile_row_pairs_in(mobile_body)
    missing = PRE_MOBILE_ROW_PAIRS - post_pairs
    assert not missing, (
        f"Mobile row pairs lost in restructure (post must be superset of "
        f"pre): {missing}")


def test_shared_verdict_semantics_section_present():
    """AC6: `## Shared Verdict Semantics` section with composition rules."""
    text = _read()
    assert re.search(r"^##\s+Shared Verdict Semantics\b",
                     text, re.MULTILINE), \
        "Expected `## Shared Verdict Semantics` H2 section"
    body = _section_body(text, "##", "Shared Verdict Semantics")
    # Must mention the per-target enum AND the composite verdicts.
    assert "PASS" in body and "FAIL" in body and "SKIP" in body, \
        "Shared Verdict Semantics missing per-target enum"
    assert "VERIFIED" in body, "Composite verdicts missing"
    assert "UNVERIFIED" in body, "Composite verdicts missing"
