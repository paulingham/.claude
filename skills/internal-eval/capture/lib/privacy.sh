#!/usr/bin/env bash
# Privacy banner gate. Exits 1 if marker absent, 0 (silent) if present.
set -u

privacy_banner() {
  cat <<'EOF' >&2
===============================================================
 PRIVACY BANNER — /internal-eval capture backfill
 This command captures real harness content from merged PRs:
   • PR numbers, titles, descriptions
   • full PR diffs (golden-diff/*.patch)
   • pre-merge file contents (context/)
 All output lands under eval/cases/.candidates/ (gitignored).
 Nothing is pushed. Nothing leaves this machine unless you
 commit and push it yourself.
 To acknowledge, create the marker file and re-run:
   touch eval/.privacy-acked
===============================================================
EOF
}

privacy_gate() {
  [ -f "eval/.privacy-acked" ] && return 0
  privacy_banner
  exit 1
}
