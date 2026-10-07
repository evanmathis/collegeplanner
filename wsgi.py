"""Entry point for the live site: `gunicorn wsgi:app` (DreamHost VPS) or the WSGI file
on PythonAnywhere. Settings come from .env next to this file (see README)."""
from werkzeug.middleware.proxy_fix import ProxyFix

from planner import create_app

# The host's web server sits in front of the app and passes on the original
# https:// address, so links like the calendar feed URL come out right.
app = ProxyFix(create_app(), x_proto=1, x_host=1)
