from datetime import date, datetime

from . import db

SCHOOL_STATUSES = ["Idea", "Considering", "Applying", "Submitted", "Admitted",
                   "Waitlisted", "Denied", "Committed"]
FEE_WAIVER_STATUSES = ["Not checked", "Eligible", "Requested", "Granted", "Not eligible"]
DEADLINE_KINDS = ["Application", "Music", "Financial aid", "Scholarship", "Other"]
TASK_CATEGORIES = ["Application", "High school", "Music", "Financial aid", "Testing", "General"]
QUESTION_TOPICS = ["General", "Application", "Music", "Financial aid", "Scholarships"]
SCHOLARSHIP_STATUSES = ["Researching", "Applying", "Submitted", "Awarded", "Not awarded"]


class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    system = db.Column(db.String(40), default="")
    degree = db.Column(db.String(255), default="")
    app_platform = db.Column(db.String(80), default="")
    music_requirement = db.Column(db.Text, default="")
    program_link = db.Column(db.String(500), default="")
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="Considering")
    fee_waiver = db.Column(db.String(30), default="Not checked")
    # How well the imported facts were checked ("verified", "partly verified", ...).
    data_status = db.Column(db.String(40), default="")

    deadlines = db.relationship("Deadline", backref="school", cascade="all, delete-orphan",
                                order_by="Deadline.due_date")
    tasks = db.relationship("Task", backref="school", cascade="all, delete-orphan",
                            order_by="Task.done, Task.due_date")
    links = db.relationship("Link", backref="school", cascade="all, delete-orphan")
    questions = db.relationship("Question", backref="school", cascade="all, delete-orphan",
                                order_by="Question.created_at.desc()")

    def open_items(self):
        return ([d for d in self.deadlines if not d.done]
                + [t for t in self.tasks if not t.done])

    def progress(self):
        total = len(self.deadlines) + len(self.tasks)
        done = total - len(self.open_items())
        return done, total

    def next_deadline(self):
        upcoming = [d for d in self.deadlines if not d.done and d.due_date >= date.today()]
        return min(upcoming, key=lambda d: d.due_date) if upcoming else None


class Deadline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    kind = db.Column(db.String(30), default="Application")
    done = db.Column(db.Boolean, default=False, nullable=False)
    notes = db.Column(db.Text, default="")


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    category = db.Column(db.String(30), default="General")
    done = db.Column(db.Boolean, default=False, nullable=False)
    notes = db.Column(db.Text, default="")


class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=True)
    label = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(500), nullable=False)


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=True)
    topic = db.Column(db.String(30), default="General")
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, default="")
    done = db.Column(db.Boolean, default=False, nullable=False)  # answered / resolved
    created_at = db.Column(db.DateTime, default=datetime.now)


class Scholarship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    provider = db.Column(db.String(255), default="")
    amount = db.Column(db.String(80), default="")
    deadline = db.Column(db.Date, nullable=True)
    url = db.Column(db.String(500), default="")
    requirements = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="Researching")
    notes = db.Column(db.Text, default="")
