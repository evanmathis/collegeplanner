import re
from datetime import date, datetime, timedelta

import pytest

from planner import create_app, db, game
from planner.models import Deadline, GameLog, Payout, Task

TODAY = date.today()


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "PLANNER_PASSWORD": "pw", "PARENT_PIN": "1234",
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'g.db'}"})
    with app.app_context():
        game.set_setting("start_date", (TODAY - timedelta(days=30)).isoformat())
        db.session.add_all([
            Deadline(title="Big application", due_date=TODAY + timedelta(days=10),
                     kind="Application", points_min=20, points_max=30),
            Task(title="Small step", due_date=TODAY + timedelta(days=2),
                 category="High school", points_min=5, points_max=10),
            Task(title="Already late", due_date=TODAY - timedelta(days=1),
                 category="General", points_min=10, points_max=10),
            Task(title="Before the game", due_date=TODAY - timedelta(days=60),
                 category="General", points_min=50, points_max=50),
            Task(title="Not in the game", category="General", points_min=0, points_max=0),
        ])
        db.session.commit()
    return app


def login(app, who, pin=""):
    c = app.test_client()
    c.post("/login", data={"password": "pw", "who": who, "pin": pin})
    return c


def token(c):
    return re.search(r'name="_csrf" value="([^"]+)"',
                     c.get("/scoreboard").get_data(as_text=True)).group(1)


def ids(app):
    with app.app_context():
        return {t.title: (("deadline" if isinstance(t, Deadline) else "task"), t.id)
                for t in Deadline.query.all() + Task.query.all()}


def test_parent_needs_pin(app):
    c = login(app, "Evan", pin="wrong")
    assert c.get("/scoreboard").status_code == 302
    c = login(app, "Evan", pin="1234")
    assert "Game settings" in c.get("/scoreboard").get_data(as_text=True)
    cian = login(app, "Cian")
    html = cian.get("/scoreboard").get_data(as_text=True)
    assert "Game settings" not in html
    assert cian.get("/game/settings").status_code == 403


def test_pot_split_and_money_never_negative(app):
    with app.app_context():
        board = game.scoreboard()
        # Counted: 30 + 10 + 10 = 50 points; "before the game" and 0-point items aren't.
        assert board["total_points"] == 50
        m = board["money"]
        assert m["open"] == 200 and m["missed"] == 50 and m["earned"] == 0
        assert round(sum(m.values()), 2) == 250
        assert all(v >= 0 for v in m.values())


def test_done_on_time_then_verified_earns(app):
    k = ids(app)
    cian, evan = login(app, "Cian"), login(app, "Evan", "1234")
    kind, i = k["Big application"]
    cian.post(f"/{kind}/{i}/toggle", data={"_csrf": token(cian), "next": "/"})
    with app.app_context():
        assert game.scoreboard()["money"]["pending"] == 150
    # Cian can't verify his own work.
    r = cian.post(f"/verify/{kind}/{i}", data={"_csrf": token(cian), "action": "verify"})
    assert r.status_code == 403
    evan.post(f"/verify/{kind}/{i}",
              data={"_csrf": token(evan), "action": "verify", "points": "25"})
    with app.app_context():
        board = game.scoreboard()
        assert board["money"]["earned"] == 125   # 25 points x $5
        assert board["money"]["missed"] == 75    # 10 points not awarded + the late task
        d = db.session.get(Deadline, i)
        assert d.verified_by == "Evan" and d.verify_status == "verified"
        assert GameLog.query.count() >= 2
    # Once verified, only a parent can undo it.
    cian.post(f"/{kind}/{i}/toggle", data={"_csrf": token(cian), "next": "/"})
    with app.app_context():
        assert db.session.get(Deadline, i).done


def test_points_are_kept_within_the_range(app):
    k = ids(app)
    cian, evan = login(app, "Cian"), login(app, "Evan", "1234")
    kind, i = k["Small step"]
    cian.post(f"/{kind}/{i}/toggle", data={"_csrf": token(cian), "next": "/"})
    evan.post(f"/verify/{kind}/{i}",
              data={"_csrf": token(evan), "action": "verify", "points": "999"})
    with app.app_context():
        assert db.session.get(Task, i).verified_points == 10


def test_send_back_lets_cian_redo_it(app):
    k = ids(app)
    cian, evan = login(app, "Cian"), login(app, "Evan", "1234")
    kind, i = k["Small step"]
    cian.post(f"/{kind}/{i}/toggle", data={"_csrf": token(cian), "next": "/"})
    evan.post(f"/verify/{kind}/{i}", data={"_csrf": token(evan), "action": "reject",
                                           "note": "Upload the PDF too"})
    html = cian.get("/tasks").get_data(as_text=True)
    assert "Upload the PDF too" in html
    with app.app_context():
        t = db.session.get(Task, i)
        assert not t.done and t.verify_status == "rejected"
        assert game.state(t, TODAY) == "open"


def test_marked_done_late_is_missed(app):
    k = ids(app)
    cian = login(app, "Cian")
    kind, i = k["Already late"]
    cian.post(f"/{kind}/{i}/toggle", data={"_csrf": token(cian), "next": "/"})
    with app.app_context():
        assert game.state(db.session.get(Task, i), TODAY) == "missed"


def test_done_on_time_but_verified_later_still_counts(app):
    with app.app_context():
        t = Task.query.filter_by(title="Already late").one()
        t.done, t.done_at = True, datetime.combine(t.due_date, datetime.min.time())
        t.verify_status, t.verified_points = "verified", 10
        db.session.commit()
        assert game.state(t, TODAY) == "earned"


def test_cian_cannot_change_points_or_delete_game_items(app):
    k = ids(app)
    cian = login(app, "Cian")
    kind, i = k["Big application"]
    assert cian.get(f"/{kind}/{i}/edit").status_code == 403
    assert cian.post(f"/{kind}/{i}/delete", data={"_csrf": token(cian)}).status_code == 403
    # His own new tasks start outside the game, whatever he sends.
    cian.post("/task/new", data={"_csrf": token(cian), "title": "My idea",
                                 "category": "General", "points_max": "500"})
    with app.app_context():
        assert Task.query.filter_by(title="My idea").one().points_max == 0


def test_parent_new_task_gets_default_points(app):
    evan = login(app, "Evan", "1234")
    evan.post("/task/new", data={"_csrf": token(evan), "title": "Ask for a letter",
                                 "category": "Application"})
    with app.app_context():
        t = Task.query.filter_by(title="Ask for a letter").one()
        assert (t.points_min, t.points_max) == game.TASK_POINTS["Application"]


def test_pause_excuse_and_payouts(app):
    k = ids(app)
    evan = login(app, "Evan", "1234")
    evan.post("/game/settings", data={"_csrf": token(evan), "action": "pause"})
    with app.app_context():
        board = game.scoreboard()
        assert board["paused"] and board["money"]["open"] == 0  # future items paused
    evan.post("/game/settings", data={"_csrf": token(evan), "action": "resume"})
    kind, i = k["Already late"]
    evan.post(f"/verify/{kind}/{i}", data={"_csrf": token(evan), "action": "excuse"})
    with app.app_context():
        board = game.scoreboard()
        assert board["money"]["missed"] == 0 and board["total_points"] == 40
    evan.post("/game/payout", data={"_csrf": token(evan), "amount": "12.50"})
    with app.app_context():
        assert Payout.query.one().amount_cents == 1250
        assert game.scoreboard()["owed"] == 0  # never negative
    evan.post("/game/settings", data={"_csrf": token(evan), "action": "rules",
                                      "pot": "100",
                                      "start_date": (TODAY - timedelta(days=30)).isoformat()})
    with app.app_context():
        assert game.scoreboard()["pot"] == 100


def test_header_shows_money_at_stake(app):
    html = login(app, "Cian").get("/").get_data(as_text=True)
    assert "at stake in 2 weeks" in html and "u-stake" in html


def test_streak(app):
    with app.app_context():
        for t in Task.query.all() + Deadline.query.all():
            if t.title in ("Small step",):
                t.done, t.done_at = True, datetime.now()
                t.verify_status, t.verified_points = "verified", 10
        db.session.commit()
        board = game.scoreboard()
        # "Already late" (missed) comes first by date, then "Small step" (earned).
        assert board["streak"] == 1 and board["best_streak"] == 1
