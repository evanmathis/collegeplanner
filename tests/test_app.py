import os
import re
from datetime import date

import pytest

from planner import create_app, db
from planner.models import Deadline, Question, School, Task
from planner.seed import (DATA_DIR, import_more_schools, import_schools, import_suggestions,
                          import_tasks, parse_dates)


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True,
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
                      "PLANNER_PASSWORD": ""})
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf(client):
    html = client.get("/aid").get_data(as_text=True)
    return re.search(r'name="_csrf" value="([^"]+)"', html).group(1)


def seed(app):
    with app.app_context():
        import_schools(os.path.join(DATA_DIR, "schools.csv"))
        import_suggestions(os.path.join(DATA_DIR, "suggestions.csv"))
        import_tasks(os.path.join(DATA_DIR, "tasks.csv"))
        import_more_schools(os.path.join(DATA_DIR, "more_schools.csv"))


def test_parse_dates_reuses_year():
    assert parse_dates("In-person auditions 2027-02-06, 02-13, 02-20") == [
        date(2027, 2, 6), date(2027, 2, 13), date(2027, 2, 20)]
    assert parse_dates("none") == []


def test_seed_is_idempotent(app):
    seed(app)
    with app.app_context():
        counts = (School.query.count(), Deadline.query.count(), Task.query.count())
    seed(app)
    with app.app_context():
        assert (School.query.count(), Deadline.query.count(), Task.query.count()) == counts
        assert School.query.filter_by(status="Applying").count() == 9
        ucla = School.query.filter_by(name="UCLA").one()
        assert any(d.due_date == date(2026, 12, 4) for d in ucla.deadlines)
        brag = Task.query.filter(Task.title.like("Complete Brag Sheet%")).one()
        assert brag.category == "High school" and brag.due_date == date(2026, 10, 31)
        letter = Task.query.filter(Task.title.like("Request teacher letter%")).one()
        assert letter.due_date is None and "30 days before" in letter.notes


def test_every_page_renders(app, client):
    seed(app)
    for path in ["/", "/timeline", "/timeline?done=1", "/schools", "/schools/1", "/tasks",
                 "/questions", "/aid", "/school/new", "/deadline/new?f_school_id=1",
                 "/task/new?f_category=Financial+aid", "/question/new", "/scholarship/new",
                 "/link/new", "/deadline/1/edit"]:
        assert client.get(path).status_code == 200, path


def test_add_toggle_delete(app, client):
    seed(app)
    token = csrf(client)
    r = client.post("/question/new", data={"_csrf": token, "question": "What is a prescreen?",
                                           "topic": "Music", "school_id": "1", "next": "/questions"})
    assert r.status_code == 302 and r.location.endswith("/questions")
    with app.app_context():
        q = Question.query.one()
        assert q.school.name and not q.done
        qid = q.id
    client.post(f"/question/{qid}/toggle", data={"_csrf": token})
    with app.app_context():
        assert db.session.get(Question, qid).done
    client.post(f"/question/{qid}/delete", data={"_csrf": token})
    with app.app_context():
        assert Question.query.count() == 0


def test_validation_keeps_record_unchanged(app, client):
    seed(app)
    token = csrf(client)
    r = client.post("/school/1/edit", data={"_csrf": token, "name": "UC Berkeley"})
    assert r.status_code == 200 and b"already exists" in r.data
    with app.app_context():
        assert db.session.get(School, 1).name == "UCLA"


def test_post_without_csrf_is_rejected(client):
    assert client.post("/task/new", data={"title": "x"}).status_code == 400


def test_password_required_when_set(tmp_path):
    app = create_app({"TESTING": True, "PLANNER_PASSWORD": "pw",
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'p.db'}"})
    c = app.test_client()
    assert c.get("/").status_code == 302
    c.get("/login")
    c.post("/login", data={"password": "pw"})
    assert c.get("/").status_code == 200


def test_calendar_download_and_feed(tmp_path):
    app = create_app({"TESTING": True, "PLANNER_PASSWORD": "pw", "CALENDAR_TOKEN": "s3cret",
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'c.db'}"})
    seed(app)
    c = app.test_client()
    # Download needs a login; the feed works with only the token.
    assert c.get("/calendar.ics").status_code == 302
    assert c.get("/calendar/wrong.ics").status_code == 404
    r = c.get("/calendar/s3cret.ics")
    assert r.status_code == 200 and r.mimetype == "text/calendar"
    body = r.get_data(as_text=True)
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert "SUMMARY:UCLA: Music application / portfolio due" in body
    assert "DTSTART;VALUE=DATE:20261204" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    with app.app_context():
        dl = Deadline.query.filter_by(due_date=date(2026, 12, 4)).one()
        assert f"UID:deadline-{dl.id}@college-planner" in body
        dl.done = True
        db.session.commit()
    assert "20261204" not in c.get("/calendar/s3cret.ics").get_data(as_text=True)
    c.post("/login", data={"password": "pw"})
    r = c.get("/calendar.ics")
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"]
    assert c.get("/calendar").status_code == 200


def test_calendar_feed_off_without_token(client):
    assert client.get("/calendar/anything.ics").status_code == 404
    assert b"feed is off" in client.get("/calendar").data


def test_keep_remove_restore(app, client):
    seed(app)
    with app.app_context():
        usc = School.query.filter_by(name="USC Thornton").one()
        assert usc.status == "Considering" and not usc.on_list
        usc_id = usc.id
        madrid = School.query.filter(School.name.like("Real Conservatorio%")).one()
        assert madrid.system == "Abroad" and "visa" in madrid.abroad_steps
        assert School.query.filter_by(status="Idea").count() == 0
    token = csrf(client)
    # Undecided schools stay off the timeline.
    assert b"USC Thornton" not in client.get("/timeline").data
    assert b"USC Thornton" in client.get("/schools").data
    client.post(f"/schools/{usc_id}/choose", data={"_csrf": token, "choice": "keep"},
                follow_redirects=True)  # shows the flash message now, not on the next page
    assert b"USC Thornton" in client.get("/timeline").data
    client.post(f"/schools/{usc_id}/choose", data={"_csrf": token, "choice": "remove"},
                follow_redirects=True)  # shows the flash message now, not on the next page
    assert b"USC Thornton" not in client.get("/timeline").data
    with app.app_context():
        assert db.session.get(School, usc_id).status == "Removed"  # kept, not deleted
    seed(app)  # re-running the import keeps Cian's choice
    with app.app_context():
        assert db.session.get(School, usc_id).status == "Removed"
    client.post(f"/schools/{usc_id}/choose", data={"_csrf": token, "choice": "restore"},
                follow_redirects=True)  # shows the flash message now, not on the next page
    with app.app_context():
        assert db.session.get(School, usc_id).status == "Considering"
    assert client.get(f"/schools/{usc_id}").status_code == 200


def test_old_database_gets_new_columns(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE school (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL UNIQUE, "
                "status VARCHAR(30))")
    con.execute("INSERT INTO school (name, status) VALUES ('UCLA', 'Applying')")
    con.commit()
    con.close()
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{path}"})
    with app.app_context():
        ucla = School.query.one()
        assert ucla.abroad_steps is None and ucla.on_list
    assert app.test_client().get("/schools/1").status_code == 200
