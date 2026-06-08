import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "hooks"

def _hook_files():
    return [f for f in HOOKS_DIR.glob("*.sh") if not f.name.startswith("_")]

def test_every_hook_has_enforces_comment():
    missing = []
    for f in _hook_files():
        head = "\n".join(f.read_text().splitlines()[:30])
        if not re.search(r"^#\s*enforces:", head, re.MULTILINE):
            missing.append(f.name)
    assert not missing, f"Hooks missing # enforces: {missing}"

def test_every_hook_has_protects_comment():
    missing = []
    for f in _hook_files():
        head = "\n".join(f.read_text().splitlines()[:30])
        if not re.search(r"^#\s*protects:", head, re.MULTILINE):
            missing.append(f.name)
    assert not missing, f"Hooks missing # protects: {missing}"

def test_enforces_target_resolves_to_real_rule_file():
    bad = []
    for f in _hook_files():
        head = "\n".join(f.read_text().splitlines()[:30])
        m = re.search(r"^#\s*enforces:\s*(\S+)", head, re.MULTILINE)
        if m:
            rule_path = m.group(1).split(":")[0]
            if not (ROOT / rule_path).exists():
                bad.append((f.name, rule_path))
    assert not bad, f"Bad rule references: {bad}"

def test_protects_value_is_non_empty():
    """`# protects:` is a free-form annotation: it may name skills (e.g.
    `pipeline, forensics`), the `all-skills` meta-token, or describe the
    concern the hook guards in prose (e.g. `root working tree integrity`,
    `codebase-map-rebuild`). The harness convention does NOT require it to
    resolve to a skill directory — many hooks legitimately protect a process
    or invariant, not a skill. The enforced contract is therefore presence +
    non-emptiness; typo'd *rule-file* references are caught separately by
    test_enforces_target_resolves_to_real_rule_file.
    """
    empty = []
    for f in _hook_files():
        head = "\n".join(f.read_text().splitlines()[:30])
        m = re.search(r"^#\s*protects:\s*(.+)$", head, re.MULTILINE)
        if m and not m.group(1).strip():
            empty.append(f.name)
    assert not empty, f"Hooks with empty # protects: value: {empty}"
