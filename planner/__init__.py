"""College Planner: one place for Cian's schools, deadlines, tasks, aid and questions."""
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    default_db = "sqlite:///" + os.path.join(app.instance_path, "planner.db")
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", default_db),
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

    with app.app_context():
        db.create_all()
        add_missing_columns()
        rename_old_statuses()

    return app


def rename_old_statuses():
    """Scholarship statuses were renamed; carry Cian's old choices over."""
    from .models import OLD_SCHOLARSHIP_STATUSES, Scholarship

    for old, new in OLD_SCHOLARSHIP_STATUSES.items():
        Scholarship.query.filter_by(status=old).update({"status": new})
    db.session.commit()


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
