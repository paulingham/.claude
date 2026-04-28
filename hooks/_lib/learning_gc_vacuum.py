"""VACUUM the SQLite memory DB via the sqlite3 CLI.

Returns True on success, False when the DB file is missing or the
``sqlite3`` CLI is unavailable. Subprocess timeout is narrow-caught to
avoid swallowing unrelated exceptions.
"""
import shutil
import subprocess
from pathlib import Path


def _invoke_vacuum(cli: str, db_path: Path) -> bool:
    try:
        result = subprocess.run(
            [cli, str(db_path), "VACUUM;"],
            capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def vacuum_db(db_path) -> bool:
    db_path = Path(db_path)
    cli = shutil.which("sqlite3")
    if not db_path.exists() or cli is None:
        return False
    return _invoke_vacuum(cli, db_path)
