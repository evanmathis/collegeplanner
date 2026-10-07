"""Entry point for DreamHost's Passenger.

DreamHost runs this file with its system Python. If our virtualenv's Python
exists, re-launch under it so the packages from requirements.txt are available.
Settings come from a .env file next to this one (see README); create_app() reads it.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INTERP = os.path.join(HERE, "venv", "bin", "python3")
if os.path.exists(INTERP) and sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.insert(0, HERE)

from planner import create_app  # noqa: E402

application = create_app()
