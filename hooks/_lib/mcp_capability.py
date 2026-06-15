"""MCP capability detection: parse, dedup, classify, and manifest writer.

WHY: 'claude mcp list' has no --json flag; line-parse only.
Line format: <name>: <endpoint> - <status_raw>
Endpoint may contain ' - ' in flag args (e.g. --language ts).
"""
import fnmatch
import json
import re
from datetime import datetime, timezone
from pathlib import Path

_RULES_PATH = Path(__file__).parent / "capability-rules.json"
_NOISE = (
    "Checking MCP server health", "MCP Config Diagnostics",
    "For help", "[Contains warnings]", " ├", " └", " │",
)
# ---------------------------------------------------------------------------


def _is_noise(line: str) -> bool:
    return not line or any(line.startswith(p) for p in _NOISE)
# ---------------------------------------------------------------------------
# WHY: split(': ',1) gives name; never first-split on ' - ' (flags use it)


def _split_name(line: str) -> tuple | None:
    if ": " not in line:
        return None
    name, rest = line.split(": ", 1)
    return name.strip(), rest
# ---------------------------------------------------------------------------
# WHY: rsplit(' - ',1) isolates rightmost status even when endpoint has ' - '


def _split_status(rest: str) -> tuple | None:
    if " - " not in rest:
        return None
    ep, st = rest.rsplit(" - ", 1)
    return ep.strip(), st.strip()
# ---------------------------------------------------------------------------


def _assemble_entry(name: str, rest: str) -> dict | None:
    parts = _split_status(rest)
    if parts is None:
        return None
    ep, st = parts
    return {"name": name, "endpoint": ep, "status_raw": st}
# ---------------------------------------------------------------------------


def _parse_valid_line(line: str) -> dict | None:
    pair = _split_name(line)
    if pair is None:
        return None
    name, rest = pair
    return _assemble_entry(name, rest)
# AC1: parse one server line or return None for noise/malformed


def parse_mcp_list_line(line: str) -> dict | None:
    if _is_noise(line):
        return None
    return _parse_valid_line(line)
# AC1b: map status symbol to connected|needs-auth|pending|absent


def normalize_status(raw: str) -> str:
    if raw.startswith("✔"):
        return "connected"
    if raw.startswith("!"):
        return "needs-auth"
    if raw.startswith("⏸"):
        return "pending"
    return "absent"
# ---------------------------------------------------------------------------


def _bare(name: str) -> str:
    return re.sub(r"^plugin:[^:]+:", "", name)
# ---------------------------------------------------------------------------


def _is_prefixed(name: str) -> bool:
    return name.startswith("plugin:")
# WHY: plugin:harness:X (Connected, expanded path) beats bare X (Pending shadow)


def _winner(existing: dict, candidate: dict) -> dict:
    if _is_prefixed(candidate["name"]) and not _is_prefixed(existing["name"]):
        return candidate
    return existing
# ---------------------------------------------------------------------------


def _dedup_index(servers: list) -> dict:
    by_bare: dict = {}
    for s in servers:
        key = _bare(s["name"])
        by_bare[key] = _winner(by_bare[key], s) if key in by_bare else s
    return by_bare
# AC1c: keep prefixed/expanded entry; drop bare-unresolved shadow


def deduplicate_servers(servers: list) -> list:
    return list(_dedup_index(servers).values())
# AC1d: parse full 'claude mcp list' output and deduplicate


def parse_mcp_list(raw: str) -> list:
    entries = [parse_mcp_list_line(l.strip()) for l in raw.splitlines()]
    return deduplicate_servers([e for e in entries if e is not None])
# ---------------------------------------------------------------------------


def load_seed_rules() -> list:
    return json.loads(_RULES_PATH.read_text())["rules"]
# ---------------------------------------------------------------------------


def _match_override(name: str, overrides: dict) -> str | None:
    return overrides.get(name)
# ---------------------------------------------------------------------------


def _match_name_regex(name: str, rules: list) -> str | None:
    for rule in rules:
        if any(re.search(p, name) for p in rule.get("name_regex", [])):
            return rule["capability"]
    return None
# ---------------------------------------------------------------------------


def _tools_hit_rule(tools: list, rule: dict) -> bool:
    globs = rule.get("tool_family", [])
    return any(fnmatch.fnmatch(t, g) for t in tools for g in globs)
# ---------------------------------------------------------------------------


def _match_tool_family(tools: list, rules: list) -> str | None:
    for rule in rules:
        if _tools_hit_rule(tools, rule):
            return rule["capability"]
    return None
# AC2/AC3: override → name_regex → tool_family → unclassified


def classify_server(server: dict, rules: list, overrides: dict) -> str:
    return (
        _match_override(server["name"], overrides)
        or _match_name_regex(server["name"], rules)
        or _match_tool_family(server.get("tools", []), rules)
        or "unclassified"
    )
# ---------------------------------------------------------------------------


def _design_rule(rules: list) -> dict:
    for r in rules:
        if r.get("capability") == "design-source":
            return r
    return {}
def _resolve_adapter(name: str, rules: list) -> str:
    hints: dict = _design_rule(rules).get("adapter_hint", {})
    for pattern, adapter in hints.items():
        if re.search(pattern, name, re.IGNORECASE):
            return adapter
    return ""
def _base_entry(s: dict, status: str, overrides: dict) -> dict:
    by = "override" if s["name"] in overrides else "rules"
    return {"status": status, "server": s["name"], "classified_by": by}
def _cap_entry(s: dict, status: str, overrides: dict, cap: str = "", rules: list | None = None) -> dict:
    entry = _base_entry(s, status, overrides)
    if cap == "design-source" and rules:
        adapter = _resolve_adapter(s["name"], rules)
        if adapter:
            entry["adapter"] = adapter
    return entry
# ---------------------------------------------------------------------------


def _classify_one(s: dict, rules: list, overrides: dict) -> tuple:
    return classify_server(s, rules, overrides), normalize_status(s["status_raw"])
# ---------------------------------------------------------------------------


def _add_classified(caps: dict, unclassed: list, s: dict,
                    cap: str, status: str, overrides: dict, rules: list | None = None) -> None:
    if cap == "unclassified":
        unclassed.append({"server": s["name"], "status": status})
    else:
        caps[cap] = _cap_entry(s, status, overrides, cap=cap, rules=rules)
# ---------------------------------------------------------------------------


def _partition(servers: list, rules: list, overrides: dict) -> tuple:
    caps: dict = {}
    unclassed: list = []
    for s in servers:
        cap, status = _classify_one(s, rules, overrides)
        _add_classified(caps, unclassed, s, cap, status, overrides, rules=rules)
    return caps, unclassed
# ---------------------------------------------------------------------------


def _manifest_meta() -> dict:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "claude mcp list",
        "ttl_seconds": 3600,
    }
# AC4: build capability manifest dict from classified servers


def build_manifest(servers: list, rules: list, overrides: dict) -> dict:
    caps, unclassed = _partition(servers, rules, overrides)
    return {**_manifest_meta(), "capabilities": caps, "unclassified": unclassed}
# ---------------------------------------------------------------------------


def write_manifest(manifest: dict, manifest_path: str) -> None:
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2))
# ---------------------------------------------------------------------------


def _parse_age(path: Path) -> float:
    data = json.loads(path.read_text())
    gen = datetime.fromisoformat(data.get("generated_at", ""))
    return (datetime.now(timezone.utc) - gen).total_seconds()
# ---------------------------------------------------------------------------


def is_stale(manifest_path: str, ttl_seconds: int = 3600) -> bool:
    path = Path(manifest_path)
    if not path.exists():
        return True
    try:
        return _parse_age(path) > ttl_seconds
    except Exception:
        return True
