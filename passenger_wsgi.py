"""Entry point for Passenger, used by control panels' "Setup Python App" /
"Python Selector" (cPanel, CloudLinux, Plesk). Point the app's startup file at
this file and its entry point at `application`. Settings come from .env.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# If you made the virtualenv yourself at venv/ (instead of the control panel making
# one), run under it so the packages from requirements.txt are available.
INTERP = os.path.join(HERE, "venv", "bin", "python3")
if os.path.exists(INTERP) and sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.insert(0, HERE)

from planner import create_app  # noqa: E402

application = create_app()
