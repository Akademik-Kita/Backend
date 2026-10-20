"""Bootstrap application dependencies without modifying the database."""

import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("Gunakan Python 3.11 atau lebih baru")
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        venv.create(ROOT / ".venv", with_pip=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True
    )
    print("Environment siap. Jalankan python -m app.cli migrate lalu uvicorn app.main:app.")


if __name__ == "__main__":
    main()
