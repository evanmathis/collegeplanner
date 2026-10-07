import hmac
import secrets
from collections import OrderedDict
from datetime import date, timedelta

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, session, url_for)

from . import db
from .models import (DEADLINE_KINDS, FEE_WAIVER_STATUSES, QUESTION_TOPICS,
                     SCHOLARSHIP_STATUSES, SCHOOL_STATUSES, TASK_CATEGORIES, Deadline,
                     Link, Question, Scholarship, School, Task)

bp = Blueprint("planner", __name__)

# One form definition per record type: (field, label, input type, choices).
# "school" renders a dropdown of schools plus "All schools / general".
FORMS = {
    "school": (School, "School", [
        ("name", "Name", "text", None),
        ("system", "System", "select", ["UC", "CSU", "Out of state", "Other"]),
        ("status", "Status", "select", SCHOOL_STATUSES),
        ("degree", "Degree / program", "text", None),
        ("app_platform", "Application platform", "text", None),
        ("music_requirement", "Music requirement (portfolio, audition...)", "textarea", None),
        ("program_link", "Program page", "url", None),
        ("fee_waiver", "Application fee waiver", "select", FEE_WAIVER_STATUSES),
        ("notes", "Notes", "textarea", None),
    ]),
    "deadline": (Deadline, "Deadline", [
        ("title", "What is due", "text", None),
        ("due_date", "Due date", "date", None),
        ("school_id", "School", "school", None),
        ("kind", "Type", "select", DEADLINE_KINDS),
        ("notes", "Notes", "textarea", None),
        ("done", "Done", "checkbox", None),
    ]),
    "task": (Task, "Task", [
        ("title", "Task", "text", None),
        ("due_date", "Do by (optional)", "date", None),
        ("school_id", "School", "school", None),
        ("category", "Category", "select", TASK_CATEGORIES),
        ("notes", "Notes", "textarea", None),
        ("done", "Done", "checkbox", None),
    ]),
    "link": (Link, "Link", [
        ("label", "Label", "text", None),
        ("url", "URL", "url", None),
        ("school_id", "School", "school", None),
    ]),
    "question": (Question, "Question", [
        ("question", "Question", "textarea", None),
        ("topic", "Topic", "select", QUESTION_TOPICS),
        ("school_id", "School", "school", None),
        ("answer", "Answer / what we found out", "textarea", None),
        ("done", "Answered", "checkbox", None),
    ]),
    "scholarship": (Scholarship, "Scholarship", [
        ("name", "Name", "text", None),
        ("provider", "Offered by", "text", None),
        ("amount", "Amount", "text", None),
        ("deadline", "Deadline", "date", None),
        ("url", "Link", "url", None),
        ("requirements", "Requirements", "textarea", None),
        ("status", "Status", "select", SCHOLARSHIP_STATUSES),
        ("notes", "Notes", "textarea", None),
    ]),
}
REQUIRED = {"name", "title", "label", "url", "question", "due_date"}


# ---------- login and CSRF ----------

@bp.before_app_request
def guard():
    if request.endpoint in ("planner.login", "static"):
        return None
    password = current_app.config["PLANNER_PASSWORD"]
    if password and not session.get("logged_in"):
        return redirect(url_for("planner.login", next=request.full_path))
    if request.method == "POST":
        token = request.form.get("_csrf", "")
        if not token or not hmac.compare_digest(token, session.get("_csrf", "")):
            abort(400, "Form expired. Go back, reload the page and try again.")
    return None


@bp.app_context_processor
def inject_globals():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return {"csrf_token": session["_csrf"], "today": date.today(),
            "login_enabled": bool(current_app.config["PLANNER_PASSWORD"])}


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        expected = current_app.config["PLANNER_PASSWORD"]
        if expected and hmac.compare_digest(request.form.get("password", ""), expected):
            session["logged_in"] = True
            session.permanent = True
            return redirect(safe_next(request.args.get("next")))
        flash("That password didn't match.")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("planner.login"))


def safe_next(target, fallback=None):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return fallback or url_for("planner.dashboard")


# ---------- pages ----------

def timeline_items(include_done=False):
    """Everything with a date, as dicts sorted by date."""
    items = []
    for d in Deadline.query.all():
        if include_done or not d.done:
            items.append(dict(kind="deadline", obj=d, date=d.due_date, title=d.title,
                              label=d.kind, school=d.school, done=d.done))
    for t in Task.query.filter(Task.due_date.isnot(None)).all():
        if include_done or not t.done:
            items.append(dict(kind="task", obj=t, date=t.due_date, title=t.title,
                              label="Task", school=t.school, done=t.done))
    for s in Scholarship.query.filter(Scholarship.deadline.isnot(None)).all():
        finished = s.status in ("Submitted", "Awarded", "Not awarded")
        if include_done or not finished:
            items.append(dict(kind="scholarship", obj=s, date=s.deadline, title=s.name,
                              label="Scholarship", school=None, done=finished))
    items.sort(key=lambda i: (i["date"], i["title"]))
    return items


@bp.route("/")
def dashboard():
    today = date.today()
    items = timeline_items()
    overdue = [i for i in items if i["date"] < today]
    soon = [i for i in items if today <= i["date"] <= today + timedelta(days=30)]
    schools = School.query.filter(School.status != "Idea").order_by(School.name).all()
    open_tasks = Task.query.filter_by(done=False).count()
    open_questions = Question.query.filter_by(done=False).count()
    return render_template("dashboard.html", overdue=overdue, soon=soon, schools=schools,
                           open_tasks=open_tasks, open_questions=open_questions)


@bp.route("/timeline")
def timeline():
    show_done = request.args.get("done") == "1"
    months = OrderedDict()
    for item in timeline_items(include_done=show_done):
        months.setdefault(item["date"].strftime("%B %Y"), []).append(item)
    return render_template("timeline.html", months=months, show_done=show_done)


@bp.route("/schools")
def schools():
    rows = School.query.order_by(School.name).all()
    active = [s for s in rows if s.status != "Idea"]
    ideas = [s for s in rows if s.status == "Idea"]
    return render_template("schools.html", active=active, ideas=ideas)


@bp.route("/schools/<int:id>")
def school_detail(id):
    school = db.get_or_404(School, id)
    return render_template("school.html", school=school)


@bp.route("/tasks")
def tasks():
    rows = Task.query.order_by(Task.done, Task.due_date.is_(None), Task.due_date).all()
    return render_template("tasks.html", tasks=rows)


@bp.route("/questions")
def questions():
    rows = Question.query.order_by(Question.done, Question.created_at.desc()).all()
    return render_template("questions.html", questions=rows)


@bp.route("/aid")
def aid():
    aid_deadlines = (Deadline.query.filter(Deadline.kind.in_(["Financial aid", "Scholarship"]))
                     .order_by(Deadline.due_date).all())
    schools = School.query.filter(School.status != "Idea").order_by(School.name).all()
    scholarships = Scholarship.query.order_by(Scholarship.deadline.is_(None),
                                              Scholarship.deadline).all()
    aid_tasks = (Task.query.filter_by(category="Financial aid")
                 .order_by(Task.done, Task.due_date).all())
    return render_template("aid.html", aid_deadlines=aid_deadlines, schools=schools,
                           scholarships=scholarships, aid_tasks=aid_tasks,
                           fee_waiver_statuses=FEE_WAIVER_STATUSES)


@bp.route("/schools/<int:id>/fee-waiver", methods=["POST"])
def set_fee_waiver(id):
    school = db.get_or_404(School, id)
    value = request.form.get("fee_waiver")
    if value in FEE_WAIVER_STATUSES:
        school.fee_waiver = value
        db.session.commit()
    return redirect(safe_next(request.form.get("next"), url_for("planner.aid")))


# ---------- generic add / edit / delete / toggle ----------

def form_spec(kind):
    if kind not in FORMS:
        abort(404)
    return FORMS[kind]


def apply_form(obj, fields, form):
    errors = []
    for name, label, ftype, choices in fields:
        raw = form.get(name, "")
        if ftype == "checkbox":
            value = name in form
        elif ftype == "date":
            value = None
            if raw:
                try:
                    value = date.fromisoformat(raw)
                except ValueError:
                    errors.append(f"{label} isn't a valid date.")
        elif ftype == "school":
            value = int(raw) if raw.isdigit() else None
        else:
            value = raw.strip()
            if ftype == "select" and value not in choices:
                value = choices[0]
        if name in REQUIRED and value in (None, ""):
            errors.append(f"{label} is required.")
        setattr(obj, name, value)
    return errors


@bp.route("/<kind>/new", methods=["GET", "POST"])
@bp.route("/<kind>/<int:id>/edit", methods=["GET", "POST"])
def edit(kind, id=None):
    model, title, fields = form_spec(kind)
    obj = db.get_or_404(model, id) if id else model()
    if id is None and request.method == "GET":
        # Pre-fill from the query string, e.g. /task/new?f_school_id=3&f_category=Music
        for name, *_ in fields:
            value = request.args.get("f_" + name)
            if value is not None:
                setattr(obj, name, int(value) if name == "school_id" and value.isdigit()
                        else value)
    if request.method == "POST":
        errors = apply_form(obj, fields, request.form)
        if not errors and kind == "school":
            with db.session.no_autoflush:
                clash = School.query.filter(School.name == obj.name,
                                            School.id != obj.id).first()
            if clash:
                errors.append("A school with that name already exists.")
        if errors:
            for e in errors:
                flash(e)
        else:
            if id is None:
                db.session.add(obj)
            db.session.commit()
            flash(f"{title} saved.")
            fallback = (url_for("planner.school_detail", id=obj.id) if kind == "school"
                        else url_for("planner.dashboard"))
            return redirect(safe_next(request.form.get("next"), fallback))
    # Re-show what was typed even when it failed validation, then discard it.
    with db.session.no_autoflush:
        schools = School.query.order_by(School.name).all()
        html = render_template("form.html", kind=kind, title=title, fields=fields, obj=obj,
                               schools=schools, is_new=id is None,
                               next=request.values.get("next") or request.referrer or "")
    db.session.rollback()
    return html


@bp.route("/<kind>/<int:id>/delete", methods=["POST"])
def delete(kind, id):
    model, title, _ = form_spec(kind)
    obj = db.get_or_404(model, id)
    db.session.delete(obj)
    db.session.commit()
    flash(f"{title} deleted.")
    fallback = url_for("planner.schools") if kind == "school" else url_for("planner.dashboard")
    nxt = request.form.get("next", "")
    if kind == "school" and nxt.startswith(f"/schools/{id}"):
        nxt = ""
    return redirect(safe_next(nxt, fallback))


@bp.route("/<kind>/<int:id>/toggle", methods=["POST"])
def toggle(kind, id):
    if kind not in ("deadline", "task", "question"):
        abort(404)
    model = FORMS[kind][0]
    obj = db.get_or_404(model, id)
    obj.done = not obj.done
    db.session.commit()
    return redirect(safe_next(request.form.get("next")))
