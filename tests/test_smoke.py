"""Smoke test (2026-10-28, foundations audit): every tracked Python file compiles (syntax check).
A first safety net for a repo that had no tests; add a real-path test next to it when this code is next touched."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tracked_py():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.py"], capture_output=True, text=True, check=True).stdout
    return [ROOT / f for f in out.split() if not any(p in f for p in ("venv/", "site-packages/", "migrations/"))]


def test_every_python_file_compiles():
    files = tracked_py()
    assert files, "no Python files found"
    for f in files:
        compile(f.read_text(encoding="utf-8"), str(f), "exec")   # syntax check, writes nothing


if __name__ == "__main__":
    test_every_python_file_compiles()
    print("smoke ok")
