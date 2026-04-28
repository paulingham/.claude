"""VACUUM the SQLite memory DB via the sqlite3 CLI.

Returns True on success, False when the DB file is missing or the
``sqlite3`` CLI is unavailable. Subprocess timeout is narrow-caught to
avoid swallowing unrelated exceptions.
"""
import shutil
import subprocess
from pathlib import Path


def vacuum_db(db_path) -> bool:
    db_path = Path(db_path)
    if not db_path.exists():
        return False
    cli = shutil.which("sqlite3")
    if cli is None:
        return False
    try:
        result = subprocess.run(
            [cli, str(db_path), "VACUUM;"],
            capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0
