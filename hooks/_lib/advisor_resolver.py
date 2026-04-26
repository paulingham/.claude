"""Pure precedence engine for resolving advisor-mode dispatch decisions. No I/O.

Returns {"executor", "advisor", "fallback_reason", "source"} where `source` names
the layer that determined the decision: "env-disabled", "no-api-key",
"frontmatter-pairing", or "no-pairing-frontmatter".

This is the Path B precedent applied to advisor-mode reviews — see
`rules/thinking-defaults.md > ## Hook Behavior (Path B — current, log-only)`
for the canonical pattern. The Agent input schema does not currently expose
`advisor`; the bash wrapper is therefore log-only until the schema lands.

Future-state precedence layer NOT implemented today, but documented here so it
survives refactors and is not silently dropped at the schema-flip moment:

  runtime-advisor-unavailable -- when the advisor API call fails (503, rate
  limit, beta header rejected) the executor wrapper drops to solo-{model}.
  Cannot be implemented in this resolver because the resolver runs PreToolUse,
  before any actual API call. The runtime fallback will live in whatever
  wrapper code dispatches the Sonnet+Opus-advisor pair once the schema
  exposes `advisor`.
"""
import re

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _kv(line):
    key, _, value = line.partition(":")
    return key.strip(), value.strip()


def parse_frontmatter(text):
    match = _FRONTMATTER_RE.match(text)
    return dict(_kv(line) for line in match.group(1).splitlines() if ":" in line) if match else {}
