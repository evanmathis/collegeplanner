#!/usr/bin/python3
"""Run the College Planner as a CGI script on shared hosting (DreamHost shared).

This repository folder is itself the website folder, e.g. ~/zonelab.app/collegeplanner
for https://zonelab.app/collegeplanner/. The .htaccess next to this file sends every
request through here, so nothing else in the folder (.env, .git, code, data) can be
downloaded.
"""
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Use the app's virtualenv (venv/ in this folder) when this isn't already it.
VENV_DIR = os.path.join(APP_DIR, "venv")
VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python3")
if os.path.exists(VENV_PYTHON) and os.path.realpath(sys.prefix) != os.path.realpath(VENV_DIR):
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

sys.path.insert(0, APP_DIR)

from wsgiref.handlers import CGIHandler  # noqa: E402

from planner import create_app  # noqa: E402

flask_app = create_app()


def application(environ, start_response):
    # Apache reports the script as ".../collegeplanner/index.cgi"; links should be
    # ".../collegeplanner/timeline", without "index.cgi" in them.
    script = environ.get("SCRIPT_NAME", "")
    if script.endswith("/index.cgi"):
        environ["SCRIPT_NAME"] = script[: -len("/index.cgi")]
    return flask_app(environ, start_response)


CGIHandler().run(application)
