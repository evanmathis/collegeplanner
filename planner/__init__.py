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

    return app
