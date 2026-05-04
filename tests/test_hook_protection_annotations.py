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

def test_protects_skills_resolve_to_real_skill_dirs():
    bad = []
    for f in _hook_files():
        head = "\n".join(f.read_text().splitlines()[:30])
        m = re.search(r"^#\s*protects:\s*(.+)$", head, re.MULTILINE)
        if m:
            skills = [s.strip() for s in m.group(1).split(",")]
            for skill in skills:
                if skill in ("all-skills", "all-agent-spawning-skills"):
                    continue  # meta-references
                skill_path = ROOT / "skills" / skill / "SKILL.md"
                deferred_path = ROOT / "skills" / "_deferred" / skill / "SKILL.md"
                if not skill_path.exists() and not deferred_path.exists():
                    bad.append((f.name, skill))
    assert not bad, f"Bad skill references: {bad}"
