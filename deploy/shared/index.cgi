#!/usr/bin/python3
"""Run the College Planner as a CGI script, for shared hosting that runs Python
CGI (DreamHost shared and most Apache hosts). Copy this file and the .htaccess
next to it into the website's folder; the code itself stays outside the website
folder (APP_DIR below) so .env is never served.
"""
import os
import pwd
import sys

HOME = pwd.getpwuid(os.getuid()).pw_dir
APP_DIR = os.path.join(HOME, "collegeplanner")  # where the repo was cloned

# Use the app's virtualenv (venv/ inside APP_DIR) when this isn't already it.
VENV_PYTHON = os.path.join(APP_DIR, "venv", "bin", "python3")
if os.path.exists(VENV_PYTHON) and os.path.realpath(sys.prefix) != os.path.realpath(
        os.path.join(APP_DIR, "venv")):
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

sys.path.insert(0, APP_DIR)

from wsgiref.handlers import CGIHandler  # noqa: E402

from planner import create_app  # noqa: E402

flask_app = create_app()


def application(environ, start_response):
    # .htaccess sends every address through this script; build links without
    # "/index.cgi" in them.
    environ["SCRIPT_NAME"] = ""
    return flask_app(environ, start_response)


CGIHandler().run(application)
