"""Vercel entrypoint: the FastAPI app lives in apps/api/roundtable."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "apps" / "api"))

from roundtable.main import app  # noqa: E402,F401
