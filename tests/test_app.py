import os
import re
from datetime import date

import pytest

from planner import create_app, db
from planner.models import Deadline, Question, School, Task
from planner.seed import DATA_DIR, import_schools, import_suggestions, parse_dates


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
