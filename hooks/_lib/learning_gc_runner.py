"""Entry point for hooks/learning-gc.sh.

CLI args: project_dir retention_days db_path. Always exits 0 — errors are
logged to stderr but never block session start.
"""
import sys
from pathlib import Path

from learning_gc_archive import archive_observations
from learning_gc_state import is_gc_due, update_state
from learning_gc_vacuum import vacuum_db


def _run(project_dir: Path, retention_days: int, db_path: Path) -> None:
    gc_state = project_dir / ".gc-state.json"
    if not is_gc_due(gc_state):
        return
    obs = project_dir / "observations.jsonl"
    archive_dir = project_dir / "archive"
    archived = archive_observations(obs, archive_dir, retention_days)
    vacuumed = vacuum_db(db_path)
    update_state(gc_state)
    print(f"[learning-gc] archived={archived} vacuumed={vacuumed}",
          file=sys.stderr)


def main(argv) -> int:
    try:
        project_dir, retention, db_path = argv[1], int(argv[2]), argv[3]
        if not Path(project_dir).is_dir():
            return 0
        _run(Path(project_dir), retention, Path(db_path))
    except Exception as exc:  # noqa: BLE001
        print(f"[learning-gc] error: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
