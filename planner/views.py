import hmac
import secrets
from collections import OrderedDict
from datetime import date, timedelta

from flask import (Blueprint, Response, abort, current_app, flash, redirect,
                   render_template, request, session, url_for)

from . import db
from .ical import build_calendar
from .models import (DEADLINE_KINDS, FEE_WAIVER_STATUSES, OFF_LIST, QUESTION_TOPICS,
                     SCHOLARSHIP_STATUSES, SCHOLARSHIP_TYPES, SCHOOL_STATUSES, SCHOOL_SYSTEMS, TASK_CATEGORIES,
                     UNDECIDED, Deadline, Link, Question, Scholarship, School, Task)

bp = Blueprint("planner", __name__)

# One form definition per record type: (field, label, input type, choices).
# "school" renders a dropdown of schools plus "All schools / general".
FORMS = {
    "school": (School, "School", [
        ("name", "Name", "text", None),
        ("system", "System", "select", SCHOOL_SYSTEMS),
        ("status", "Status", "select", SCHOOL_STATUSES),
        ("country", "Country", "text", None),
        ("city", "City", "text", None),
        ("school_type", "Public or private", "select", ["", "public", "private"]),
        ("degree", "Degree / program", "text", None),
        ("app_platform", "How to apply", "text", None),
        ("app_deadline_note", "Application deadline (as the school states it)", "text", None),
        ("music_requirement", "Music requirement (portfolio, audition...)", "textarea", None),
        ("entry_term", "Starts", "text", None),
        ("language", "Language of teaching", "text", None),
        ("cost", "Rough cost per year", "text", None),
        ("us_aid", "US financial aid", "text", None),
        ("abroad_steps", "Extra steps to study abroad", "textarea", None),
        ("program_link", "Program page", "url", None),
        ("to_confirm", "Still to confirm", "textarea", None),
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
        ("category", "Type", "select", SCHOLARSHIP_TYPES),
        ("amount", "Amount", "text", None),
        ("deadline", "Deadline", "date", None),
        ("deadline_note", "Deadline as stated (if no exact date)", "text", None),
        ("url", "Info page", "url", None),
        ("apply_url", "Apply link", "url", None),
        ("applies_to", "For which schools (names separated by ;, or \"outside\")", "text", None),
        ("requirements", "Who can apply", "textarea", None),
        ("status", "Status", "select", SCHOLARSHIP_STATUSES),
        ("notes", "Notes", "textarea", None),
    ]),
}


# ---------- login and CSRF ----------

@bp.before_app_request
def guard():
    # The calendar feed is protected by the secret token in its URL instead,
    # because calendar apps can't log in.
    if request.endpoint in ("planner.login", "planner.calendar_feed", "static"):
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
            "login_enabled": bool(current_app.config["PLANNER_PASSWORD"]),
            "up_next": up_next}


def urgency(due, today=None):
    days = (due - (today or date.today())).days
    if days < 0:
        return "overdue"
    if days <= 3:
        return "urgent"
    if days <= 14:
        return "soon"
    return "later"


def up_next(limit=6):
    """For the header on every page: the next open items (kept schools only) and
    how many are overdue / due within 3 days / within 14 days."""
    items = timeline_items()
    for item in items:
        item["urgency"] = urgency(item["date"])
    counts = {u: sum(1 for i in items if i["urgency"] == u)
              for u in ("overdue", "urgent", "soon")}
    return {"items": items[:limit], "counts": counts, "total": len(items)}


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
        if d.school and not d.school.on_list:
            continue
        if include_done or not d.done:
            items.append(dict(kind="deadline", obj=d, date=d.due_date, title=d.title,
                              label=d.kind, school=d.school, done=d.done))
    for t in Task.query.filter(Task.due_date.isnot(None)).all():
        if t.school and not t.school.on_list:
            continue
        if include_done or not t.done:
            items.append(dict(kind="task", obj=t, date=t.due_date, title=t.title,
                              label="Task", school=t.school, done=t.done))
    # Only scholarships Cian marked "Interested" (or has since applied to) count.
    for s in Scholarship.query.filter(Scholarship.deadline.isnot(None)).all():
        if s.interested or (include_done and s.finished and s.status != "Skip"):
            items.append(dict(kind="scholarship", obj=s, date=s.deadline, title=s.name,
                              label="Scholarship", school=None, done=not s.interested))
    items.sort(key=lambda i: (i["date"], i["title"]))
    return items


def on_list_schools():
    return (School.query.filter(School.status.notin_(OFF_LIST))
            .order_by(School.name).all())


@bp.route("/")
def dashboard():
    today = date.today()
    items = timeline_items()
    overdue = [i for i in items if i["date"] < today]
    soon = [i for i in items if today <= i["date"] <= today + timedelta(days=30)]
    schools = on_list_schools()
    undecided = School.query.filter(School.status.in_(UNDECIDED)).count()
    open_tasks = sum(1 for t in Task.query.filter_by(done=False) if not t.school or t.school.on_list)
    open_questions = Question.query.filter_by(done=False).count()
    return render_template("dashboard.html", overdue=overdue, soon=soon, schools=schools,
                           open_tasks=open_tasks, open_questions=open_questions,
                           undecided=undecided)


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
    active = [s for s in rows if s.on_list]
    removed = [s for s in rows if s.status == "Removed"]
    groups = OrderedDict((g, []) for g in SCHOOL_SYSTEMS)
    for s in rows:
        if s.undecided:
            groups[s.system if s.system in groups else "Other"].append(s)
    deciding = [(g, items) for g, items in groups.items() if items]
    return render_template("schools.html", active=active, deciding=deciding, removed=removed)


@bp.route("/schools/<int:id>/choose", methods=["POST"])
def choose(id):
    """Cian's keep / remove choice. Removing never deletes, so it can be undone."""
    school = db.get_or_404(School, id)
    choice = request.form.get("choice")
    if choice == "keep":
        school.status = "Applying"
        flash(f"{school.name} is on your list. Its dates are now on the timeline.")
    elif choice == "remove":
        school.status = "Removed"
        flash(f"{school.name} removed. You can bring it back from the bottom of the Schools page.")
    elif choice == "restore":
        school.status = "Considering"
        flash(f"{school.name} is back under Still deciding.")
    else:
        abort(400)
    db.session.commit()
    return redirect(safe_next(request.form.get("next"), url_for("planner.schools")))


@bp.route("/schools/<int:id>")
def school_detail(id):
    school = db.get_or_404(School, id)
    return render_template("school.html", school=school)


@bp.route("/tasks")
def tasks():
    rows = Task.query.order_by(Task.done, Task.due_date.is_(None), Task.due_date).all()
    return render_template("tasks.html", tasks=[t for t in rows if not t.school or t.school.on_list])


@bp.route("/questions")
def questions():
    rows = Question.query.order_by(Question.done, Question.created_at.desc()).all()
    return render_template("questions.html", questions=rows)


@bp.route("/aid")
def aid():
    aid_deadlines = (Deadline.query.filter(Deadline.kind.in_(["Financial aid", "Scholarship"]))
                     .order_by(Deadline.due_date).all())
    schools = on_list_schools()
    rows = Scholarship.query.all()
    sch_counts = dict(total=len(rows), interested=sum(s.interested for s in rows),
                      applied=sum(s.status in ("Applied", "Awarded", "Not awarded") for s in rows))
    aid_tasks = (Task.query.filter_by(category="Financial aid")
                 .order_by(Task.done, Task.due_date).all())
    aid_deadlines = [d for d in aid_deadlines if not d.school or d.school.on_list]
    aid_tasks = [t for t in aid_tasks if not t.school or t.school.on_list]
    return render_template("aid.html", aid_deadlines=aid_deadlines, schools=schools,
                           sch_counts=sch_counts, aid_tasks=aid_tasks,
                           fee_waiver_statuses=FEE_WAIVER_STATUSES)


SCHOLARSHIP_WHEN = OrderedDict([
    ("open", "Still open"), ("30", "Due in 30 days"), ("90", "Due in 90 days"),
    ("nodate", "No set date"), ("closed", "Closed"), ("all", "Any deadline"),
])
SCHOLARSHIP_SHOW = OrderedDict([
    ("active", "All but skipped"), ("Interested", "Interested"), ("Not applied", "Not applied"),
    ("Applied", "Applied or decided"), ("Skip", "Skipped"),
])
# The status buttons on each scholarship.
SCHOLARSHIP_CHOICES = ["Not applied", "Interested", "Applied", "Skip"]


def scholarship_matches(s, when, show, school, today):
    if when == "open" and s.deadline and s.deadline < today:
        return False
    if when in ("30", "90") and not (s.deadline and today <= s.deadline
                                     <= today + timedelta(days=int(when))):
        return False
    if when == "nodate" and s.deadline:
        return False
    if when == "closed" and not (s.deadline and s.deadline < today):
        return False
    if show == "active" and s.status == "Skip":
        return False
    if show == "Applied" and s.status not in ("Applied", "Awarded", "Not awarded"):
        return False
    if show in ("Interested", "Not applied", "Skip") and s.status != show:
        return False
    if school == "outside" and (s.applies_to or "outside") != "outside":
        return False
    if isinstance(school, School) and not s.for_school(school):
        return False
    return True


@bp.route("/scholarships")
def scholarships():
    today = date.today()
    f = dict(type=request.args.get("type", ""), when=request.args.get("when", "open"),
             show=request.args.get("show", "active"), school=request.args.get("school", ""))
    if f["when"] not in SCHOLARSHIP_WHEN:
        f["when"] = "open"
    if f["show"] not in SCHOLARSHIP_SHOW:
        f["show"] = "active"
    rows = Scholarship.query.order_by(Scholarship.deadline.is_(None), Scholarship.deadline,
                                      Scholarship.name).all()
    school = (db.session.get(School, int(f["school"])) if f["school"].isdigit()
              else f["school"])
    shown = [s for s in rows
             if (not f["type"] or (s.category or "other") == f["type"])
             and scholarship_matches(s, f["when"], f["show"], school, today)]
    schools = on_list_schools()
    all_schools = School.query.order_by(School.name).all()
    tied = {s.id: [sc for sc in all_schools if s.for_school(sc)] for s in shown}
    counts = {st: sum(1 for s in rows if s.status == st) for st in SCHOLARSHIP_STATUSES}
    return render_template("scholarships.html", scholarships=shown, total=len(rows),
                           tied=tied, schools=schools, f=f, counts=counts,
                           types=SCHOLARSHIP_TYPES, whens=SCHOLARSHIP_WHEN,
                           shows=SCHOLARSHIP_SHOW, choices=SCHOLARSHIP_CHOICES,
                           filtered=f != dict(type="", when="open", show="active", school=""))


@bp.route("/scholarships/<int:id>/status", methods=["POST"])
def set_scholarship_status(id):
    s = db.get_or_404(Scholarship, id)
    value = request.form.get("status")
    if value not in SCHOLARSHIP_STATUSES:
        abort(400)
    s.status = value
    db.session.commit()
    if value == "Interested" and s.deadline:
        flash(f"{s.name} is on the timeline and calendar.")
    return redirect(safe_next(request.form.get("next"), url_for("planner.scholarships"))
                    + f"#s{s.id}")


def calendar_response(download):
    body = build_calendar(timeline_items(), url_for("planner.timeline", _external=True))
    resp = Response(body, mimetype="text/calendar")
    if download:
        resp.headers["Content-Disposition"] = "attachment; filename=college-planner.ics"
    return resp


@bp.route("/calendar")
def calendar():
    token = current_app.config["CALENDAR_TOKEN"]
    feed_url = url_for("planner.calendar_feed", token=token, _external=True) if token else ""
    return render_template("calendar.html", feed_url=feed_url,
                           webcal_url=feed_url.replace("https://", "webcal://", 1)
                           .replace("http://", "webcal://", 1),
                           count=len(timeline_items()))


@bp.route("/calendar.ics")
def calendar_download():
    return calendar_response(download=True)


@bp.route("/calendar/<token>.ics")
def calendar_feed(token):
    expected = current_app.config["CALENDAR_TOKEN"]
    if not expected or not hmac.compare_digest(token, expected):
        abort(404)
    return calendar_response(download=False)


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
                value = list(choices)[0]
        column = getattr(type(obj), name)
        limit = getattr(column.type, "length", None)
        if limit and isinstance(value, str) and len(value) > limit:
            errors.append(f"{label} is too long (at most {limit} characters).")
        if not column.nullable and ftype != "checkbox" and value in (None, ""):
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
