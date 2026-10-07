"""`flask --app planner check-db`: test the database connection and say plainly
what's wrong. Never prints the password."""
import sys

import click
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from . import db

# MySQL / MariaDB error codes and what they usually mean on DreamHost.
HINTS = {
    1044: "The user exists but has no access to this database. In the DreamHost panel "
          "(MySQL Databases), check that this user is listed under the database.",
    1045: "Wrong username or password, or this computer's address isn't allowed for this "
          "user. Re-check DB_USER / DB_PASSWORD. If this runs from your own computer, add "
          "its address under the user's Allowable Hosts in the DreamHost panel.",
    1049: "The database name is wrong (no database by that name on this server). "
          "Check DB_NAME.",
    1130: "This computer isn't allowed to connect. In the DreamHost panel, open MySQL "
          "Databases, click the user, and add this computer's public IP address under "
          "Allowable Hosts (keep %.dreamhost.com). On the DreamHost server itself this "
          "should already work.",
    2003: "Couldn't reach the database server. Check DB_HOST (use your MySQL hostname, "
          "never localhost). A new hostname can take a few minutes to start working, and "
          "DreamHost may block connections from outside its network until your address "
          "is under Allowable Hosts.",
    2005: "That hostname doesn't exist (yet). Check the spelling of DB_HOST; a new "
          "DreamHost MySQL hostname can take 5-10 minutes to appear.",
    2013: "The server dropped the connection while connecting, often because the address "
          "isn't allowed. Check Allowable Hosts in the DreamHost panel.",
}


def error_code(exc):
    orig = getattr(exc, "orig", None)
    args = getattr(orig, "args", ())
    return args[0] if args and isinstance(args[0], int) else None


def register(app):
    @app.cli.command("check-db")
    def check_db():
        """Test the database connection, tables and data (prints no secrets)."""
        url = db.engine.url
        click.echo(f"Database: {url.get_backend_name()}")
        if url.get_backend_name() == "sqlite":
            click.echo(f"  file:     {url.database}")
            click.echo("  (Set DB_HOST, DB_USER, DB_PASSWORD and DB_NAME in .env to use MySQL.)")
        else:
            click.echo(f"  host:     {url.host}{':' + str(url.port) if url.port else ''}")
            click.echo(f"  database: {url.database}")
            click.echo(f"  user:     {url.username}")
            click.echo(f"  password: {'set' if url.password else 'NOT SET'}")
        try:
            with db.engine.connect() as conn:
                version = conn.execute(text(
                    "select sqlite_version()" if url.get_backend_name() == "sqlite"
                    else "select version()")).scalar()
        except (OperationalError, ProgrammingError) as exc:
            code = error_code(exc)
            detail = str(getattr(exc.orig, "args", [""])[-1]).lower()
            if code == 2003 and any(w in detail for w in ("name or service", "nodename",
                                                          "getaddrinfo", "name resolution")):
                code = 2005  # the hostname doesn't resolve
            click.echo(f"\nCan't connect (error {code or 'unknown'}).", err=True)
            click.echo(HINTS.get(code, f"Details: {type(exc.orig).__name__}: "
                                       f"{getattr(exc.orig, 'args', [''])[-1]}"), err=True)
            sys.exit(1)
        click.echo(f"Connected. Server version {version}.")

        expected = set(db.metadata.tables)
        present = set(inspect(db.engine).get_table_names())
        missing = sorted(expected - present)
        if missing:
            click.echo(f"Missing tables: {', '.join(missing)}. Run "
                       "`python -m flask --app planner seed` to create them and load the "
                       "schools.", err=True)
            sys.exit(2)
        with db.engine.connect() as conn:
            counts = {t: conn.execute(text(f"select count(*) from {t}")).scalar()
                      for t in sorted(expected)}
        click.echo("Tables OK: " + ", ".join(f"{t} {n}" for t, n in counts.items()))
        if not counts.get("school"):
            click.echo("No schools yet. Run `python -m flask --app planner seed`.")
        else:
            click.echo("All good.")
