"""The points game: Cian earns a share of a cash pot for finishing things on time.

Rules (parents can change the pot, start date, points and pause it):
- Every deadline and task with points is a "game item". Its share of the pot is its
  maximum points divided by all items' maximum points.
- Cian marks an item done; that time decides whether it was on time (on or before
  the due date). A parent then verifies it, picking the points within its range, or
  sends it back with a note so Cian can fix it and mark it done again.
- Earned = verified points on items done on time. Missed = items not done by their
  due date (and any points a parent didn't award). Nothing ever goes negative.
- Items due before the start date, while the game was paused, for schools not on the
  list, or excused by a parent don't count either way.
- The app only tracks money; parents record what they've paid.
"""
from collections import OrderedDict
from datetime import date, datetime

from . import db
from .models import Deadline, GameLog, PausePeriod, Payout, Setting, Task

DEFAULT_POT = 250

# Default point ranges by importance: (min, max).
DEADLINE_POINTS = {"Application": (15, 25), "Music": (15, 25), "Financial aid": (10, 20),
                   "Scholarship": (5, 10), "Other": (3, 5)}
TASK_POINTS = {"Application": (5, 10), "Music": (5, 10), "Financial aid": (5, 8),
               "Testing": (5, 10), "High school": (2, 5), "General": (1, 3)}


def default_points(item):
    if isinstance(item, Deadline):
        return DEADLINE_POINTS.get(item.kind, (3, 5))
    return TASK_POINTS.get(item.category, (1, 3))


def assign_default_points():
    """Give point ranges to items that have never had any (new database or upgrade)."""
    changed = 0
    for model in (Deadline, Task):
        for item in model.query.filter(model.points_max.is_(None)):
            item.points_min, item.points_max = default_points(item)
            changed += 1
    if changed:
        db.session.commit()
    return changed


# ---------- settings ----------

def get_setting(key, default=""):
    row = db.session.get(Setting, key)
    return row.value if row and row.value not in (None, "") else default


def set_setting(key, value):
    row = db.session.get(Setting, key) or Setting(key=key)
    row.value = str(value)
    db.session.add(row)


def pot_dollars():
    try:
        return max(0, int(float(get_setting("pot", DEFAULT_POT))))
    except ValueError:
        return DEFAULT_POT


def start_date():
    value = get_setting("start_date")
    if not value:
        value = date.today().isoformat()
        set_setting("start_date", value)
        db.session.commit()
    return date.fromisoformat(value)


def is_paused():
    return PausePeriod.query.filter(PausePeriod.end.is_(None)).first() is not None


def log(who, what):
    db.session.add(GameLog(who=who or "", what=what[:500]))


# ---------- scoring ----------

def item_points(item):
    return max(0, item.points_max or 0)


def counts(item, start, pauses):
    """Whether this item is part of the game at all."""
    if item_points(item) == 0 or item.excused:
        return False
    if item.school is not None and not item.school.on_list:
        return False
    due = item.due_date
    if due is None:
        return True
    if due < start:
        return False
    for p in pauses:
        if p.start <= due and (p.end is None or due <= p.end):
            return False
    return True


def on_time(item):
    return item.done_at is not None and (item.due_date is None
                                         or item.done_at.date() <= item.due_date)


def state(item, today):
    """earned / pending / open / missed, for an item that counts."""
    if item.verify_status == "verified" and on_time(item):
        return "earned"
    if item.done and on_time(item):
        return "pending"
    if item.due_date is not None and item.due_date < today:
        return "missed"
    if item.done and not on_time(item):  # marked done, but after the due date
        return "missed"
    return "open"


def game_items():
    start, pauses = start_date(), PausePeriod.query.all()
    items = Deadline.query.all() + Task.query.all()
    return [i for i in items if counts(i, start, pauses)]


def kind_of(item):
    return "deadline" if isinstance(item, Deadline) else "task"


def group_of(item):
    if isinstance(item, Deadline):
        return f"{item.kind} deadlines"
    return f"{item.category} tasks"


def scoreboard(today=None):
    """Everything the Scoreboard page and the header need, in dollars and points."""
    today = today or date.today()
    pot = pot_dollars()
    items = game_items()
    total_points = sum(item_points(i) for i in items)
    per_point = pot / total_points if total_points else 0
    money = OrderedDict((k, 0.0) for k in ("earned", "pending", "open", "missed"))
    groups = OrderedDict()
    rows = []
    for item in items:
        st = state(item, today)
        pts = item_points(item)
        value = pts * per_point
        if st == "earned":
            got = min(item.verified_points or 0, pts) * per_point
            money["earned"] += got
            money["missed"] += value - got  # points a parent didn't award
        else:
            money[st] += value
        g = groups.setdefault(group_of(item), dict(points=0, earned=0.0, value=0.0))
        g["points"] += pts
        g["value"] += value
        if st == "earned":
            g["earned"] += min(item.verified_points or 0, pts) * per_point
        rows.append(dict(item=item, kind=kind_of(item), state=st, points=pts,
                         value=value))
    paid = sum(p.amount_cents for p in Payout.query.all()) / 100
    resolved = sorted((r for r in rows if r["state"] in ("earned", "missed")
                       and r["item"].due_date is not None),
                      key=lambda r: (r["item"].due_date, r["item"].done_at or datetime.max))
    streak = best = 0
    for r in resolved:
        streak = streak + 1 if r["state"] == "earned" else 0
        best = max(best, streak)
    return dict(
        pot=pot, total_points=total_points, per_point=per_point,
        money={k: round(max(0.0, v), 2) for k, v in money.items()},
        paid=round(paid, 2), owed=round(max(0.0, money["earned"] - paid), 2),
        groups=groups, rows=rows, streak=streak, best_streak=best,
        paused=is_paused(), start=start_date(),
    )


def stake(item, board):
    """Dollars riding on one item, or None when it isn't part of the game."""
    for r in board["rows"]:
        if r["item"] is item:
            return r["value"]
    return None
