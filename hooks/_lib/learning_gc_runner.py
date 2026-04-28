"""Entry point for hooks/learning-gc.sh.

CLI args: project_dir retention_days db_path. Always exits 0 — errors are
logged to stderr but never block session start.
"""
import sys
from pathlib import Path

from learning_gc_archive import archive_observations
from learning_gc_state import is_gc_due, update_state
from learning_gc_vacuum import vacuum_db


def _do_gc(project_dir: Path, retention_days: int, db_path: Path) -> None:
    archived = archive_observations(
        project_dir / "observations.jsonl",
        project_dir / "archive", retention_days)
    vacuumed = vacuum_db(db_path)
    update_state(project_dir / ".gc-state.json")
    print(f"[learning-gc] archived={archived} vacuumed={vacuumed}",
          file=sys.stderr)


def _run(project_dir: Path, retention_days: int, db_path: Path) -> None:
    if is_gc_due(project_dir / ".gc-state.json"):
        _do_gc(project_dir, retention_days, db_path)


def main(argv) -> int:
    try:
        project, retention, db = argv[1], int(argv[2]), argv[3]
        if Path(project).is_dir():
            _run(Path(project), retention, Path(db))
    except Exception as exc:  # noqa: BLE001
        print(f"[learning-gc] error: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
