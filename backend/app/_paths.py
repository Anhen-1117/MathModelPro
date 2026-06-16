"""
Global path constants.

All modules MUST use PROJECT_ROOT defined here.
Do NOT use os.path.dirname chains in business code.
"""

from pathlib import Path

# Project root = backend/
# _paths.py is at backend/app/_paths.py, so 2 levels up = backend/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Sanity check: ensure the marker file exists
_ROOT_MARKER = PROJECT_ROOT / ".project_root"
if not _ROOT_MARKER.exists():
    raise RuntimeError(
        f"Project root marker not found: {_ROOT_MARKER}\n"
        f"Make sure backend/.project_root exists and _paths.py is at backend/app/\n"
        f"Current PROJECT_ROOT = {PROJECT_ROOT}"
    )


def data_dir(*parts: str) -> str:
    """Sub-path under data/ directory.

    Usage:
        data_dir("config.json")       -> backend/data/config.json
        data_dir("knowledge")         -> backend/data/knowledge
        data_dir("templates", "mma")  -> backend/data/templates/mma
    """
    return str(PROJECT_ROOT / "data" / Path(*parts))


def project_dir(*parts: str) -> str:
    """Sub-path under project/ directory (task workspace).

    Usage:
        project_dir(task_id)               -> backend/project/{task_id}
        project_dir(task_id, "paper.pdf")  -> backend/project/{task_id}/paper.pdf
    """
    return str(PROJECT_ROOT / "project" / Path(*parts))


def db_path() -> str:
    """Absolute path to the SQLite database file."""
    return str(PROJECT_ROOT / "mathmodelpro.db")
