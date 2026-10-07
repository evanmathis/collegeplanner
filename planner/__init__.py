"""College Planner: one place for Cian's schools, deadlines, tasks, aid and questions."""
import os
import sys

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env_file(path=os.path.join(ROOT, ".env")):
    """Read KEY=value lines from .env into the environment (real environment
    variables win). Used on DreamHost by both the website and `flask` commands."""
    if os.path.exists(path):
        from dotenv import load_dotenv

        load_dotenv(path, override=False)


def database_url(instance_path):
    """DATABASE_URL if set; otherwise MySQL from DB_HOST / DB_USER / DB_PASSWORD /
    DB_NAME (no need to escape special characters in the password); otherwise SQLite."""
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if os.environ.get("DB_HOST"):
        from sqlalchemy.engine import URL

        return URL.create("mysql+pymysql", username=os.environ.get("DB_USER"),
                          password=os.environ.get("DB_PASSWORD"), host=os.environ["DB_HOST"],
                          port=int(os.environ["DB_PORT"]) if os.environ.get("DB_PORT") else None,
                          database=os.environ.get("DB_NAME"), query={"charset": "utf8mb4"})
    return "sqlite:///" + os.path.join(instance_path, "planner.db")


def create_app(config=None):
    if not (config or {}).get("TESTING"):
        load_env_file()
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        # Its own cookie name, so other apps on the same domain don't clash with it.
        SESSION_COOKIE_NAME="planner_session",
        SQLALCHEMY_DATABASE_URI=database_url(app.instance_path),
        # MySQL on shared hosting drops idle connections; recycle before that happens.
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 280},
        # When unset, the site is open (fine for local testing only).
        PLANNER_PASSWORD=os.environ.get("PLANNER_PASSWORD", ""),
        # Secret part of the calendar feed URL; the feed is off when unset.
        CALENDAR_TOKEN=os.environ.get("CALENDAR_TOKEN", ""),
    )
    if config:
        app.config.update(config)

    db.init_app(app)

    from . import models  # noqa: F401  (registers tables)
    from .views import bp
    from .seed import register_cli

    app.register_blueprint(bp)
    register_cli(app)
    from . import checkdb
    checkdb.register(app)

    # `flask check-db` diagnoses the connection itself, so don't fail before it runs.
    if "check-db" not in sys.argv:
        with app.app_context():
            prepare_database()

    return app


def rename_old_statuses():
    """Scholarship statuses were renamed; carry Cian's old choices over."""
    from .models import OLD_SCHOLARSHIP_STATUSES, Scholarship

    for old, new in OLD_SCHOLARSHIP_STATUSES.items():
        Scholarship.query.filter_by(status=old).update({"status": new})
    db.session.commit()


def prepare_database():
    db.create_all()
    add_missing_columns()
    rename_old_statuses()


def add_missing_columns():
    """create_all() won't add new columns to an existing table, so add them here.

    Keeps an existing planner database (local SQLite or DreamHost MySQL) working
    after an update without a separate migration tool.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    with db.engine.begin() as conn:
        for table in db.metadata.sorted_tables:
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing:
                    col_type = column.type.compile(dialect=db.engine.dialect)
                    conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"))
