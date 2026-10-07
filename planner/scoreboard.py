"""Scoreboard page and the parent-only controls of the points game."""
from datetime import date, datetime

from flask import abort, flash, redirect, render_template, request, url_for

from . import db, game
from .models import Deadline, GameLog, PausePeriod, Payout, Task
from .views import bp, current_user, is_parent, require_parent, safe_next

MODELS = {"deadline": Deadline, "task": Task}


def money(value):
    return f"${value:,.2f}".replace(".00", "")


@bp.app_template_filter("money")
def money_filter(value):
    return money(value or 0)


@bp.route("/scoreboard")
def scoreboard():
    board = game.scoreboard()
    rows = board["rows"]
    pending = sorted((r for r in rows if r["state"] == "pending"),
                     key=lambda r: r["item"].done_at or datetime.min)
    recent = sorted((r for r in rows if r["item"].verify_status == "verified"),
                    key=lambda r: r["item"].verified_at or datetime.min, reverse=True)[:8]
    upcoming = sorted((r for r in rows if r["state"] == "open" and r["item"].due_date),
                      key=lambda r: r["item"].due_date)[:6]
    missed = sorted((r for r in rows if r["state"] == "missed"),
                    key=lambda r: r["item"].due_date or date.min, reverse=True)
    sent_back = [r for r in rows if r["item"].verify_status == "rejected"
                 and r["state"] == "open"]
    logs = (GameLog.query.order_by(GameLog.at.desc()).limit(40).all()
            if is_parent() else [])
    payouts = Payout.query.order_by(Payout.paid_on.desc(), Payout.id.desc()).all()
    return render_template("scoreboard.html", board=board, pending=pending, recent=recent,
                           upcoming=upcoming, missed=missed, sent_back=sent_back,
                           logs=logs, payouts=payouts)


@bp.route("/verify/<kind>/<int:id>", methods=["POST"])
def verify(kind, id):
    require_parent()
    if kind not in MODELS:
        abort(404)
    item = db.get_or_404(MODELS[kind], id)
    who = current_user()["name"]
    action = request.form.get("action")
    note = request.form.get("note", "").strip()[:500]
    if action == "verify":
        if not item.done:
            abort(400, "Cian hasn't marked this one done yet.")
        try:
            points = int(request.form.get("points", item.points_max or 0))
        except ValueError:
            points = item.points_max or 0
        lo, hi = item.points_min or 0, item.points_max or 0
        points = max(min(points, hi), min(lo, hi))
        item.verify_status, item.verified_points = "verified", points
        item.verified_by, item.verified_at, item.verify_note = who, datetime.now(), note
        game.log(who, f"Verified {item.title}: {points} of {hi} points"
                      + (f" ({note})" if note else ""))
        flash(f"Verified: {item.title}, {points} points.")
    elif action == "reject":
        item.done, item.done_at = False, None
        item.verify_status, item.verified_points = "rejected", None
        item.verified_by, item.verified_at, item.verify_note = who, datetime.now(), note
        game.log(who, f"Sent back {item.title}" + (f": {note}" if note else ""))
        flash(f"Sent back to Cian: {item.title}.")
    elif action in ("excuse", "unexcuse"):
        item.excused = action == "excuse"
        game.log(who, ("Took out of the game: " if item.excused else "Put back in the game: ")
                 + item.title + (f" ({note})" if note else ""))
        flash(f"{'Taken out of' if item.excused else 'Back in'} the game: {item.title}.")
    else:
        abort(400)
    db.session.commit()
    return redirect(safe_next(request.form.get("next"), url_for("planner.scoreboard")))


@bp.route("/game/payout", methods=["POST"])
def payout():
    require_parent()
    raw = request.form.get("amount", "").replace("$", "").replace(",", "").strip()
    try:
        cents = round(float(raw) * 100)
    except ValueError:
        cents = 0
    if cents <= 0:
        flash("Enter the amount paid, like 25 or 12.50.")
    else:
        who = current_user()["name"]
        note = request.form.get("note", "").strip()[:255]
        db.session.add(Payout(amount_cents=cents, paid_by=who, note=note,
                              paid_on=date.today()))
        game.log(who, f"Paid Cian {money(cents / 100)}" + (f" ({note})" if note else ""))
        db.session.commit()
        flash(f"Recorded a payment of {money(cents / 100)}.")
    return redirect(url_for("planner.scoreboard") + "#paid")


@bp.route("/game/payout/<int:id>/delete", methods=["POST"])
def delete_payout(id):
    require_parent()
    p = db.get_or_404(Payout, id)
    game.log(current_user()["name"], f"Deleted a payment of {money(p.amount_cents / 100)}")
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for("planner.scoreboard") + "#paid")


@bp.route("/game/settings", methods=["GET", "POST"])
def game_settings():
    require_parent()
    who = current_user()["name"]
    if request.method == "POST":
        action = request.form.get("action")
        if action == "pause" and not game.is_paused():
            db.session.add(PausePeriod(start=date.today()))
            game.log(who, "Paused the game")
            flash("Paused. Nothing due while paused counts, either way.")
        elif action == "resume":
            for p in PausePeriod.query.filter(PausePeriod.end.is_(None)):
                p.end = date.today()
            game.log(who, "Resumed the game")
            flash("Back on.")
        elif action == "rules":
            changes = []
            try:
                pot = max(0, int(float(request.form.get("pot", game.pot_dollars()))))
                if pot != game.pot_dollars():
                    changes.append(f"pot ${game.pot_dollars()} to ${pot}")
                    game.set_setting("pot", pot)
            except ValueError:
                flash("The pot must be a number of dollars.")
            raw = request.form.get("start_date", "")
            try:
                start = date.fromisoformat(raw)
                if start != game.start_date():
                    changes.append(f"start date to {start:%b %-d, %Y}")
                    game.set_setting("start_date", start.isoformat())
            except ValueError:
                flash("Pick a valid start date.")
            if changes:
                game.log(who, "Changed " + ", ".join(changes))
                flash("Saved.")
        elif action == "points":
            changed = 0
            for model, prefix in ((Deadline, "d"), (Task, "t")):
                for item in model.query.all():
                    lo = request.form.get(f"{prefix}{item.id}_min")
                    hi = request.form.get(f"{prefix}{item.id}_max")
                    if lo is None or hi is None:
                        continue
                    try:
                        lo, hi = max(0, int(lo or 0)), max(0, int(hi or 0))
                    except ValueError:
                        continue
                    lo = min(lo, hi)
                    if (lo, hi) != (item.points_min or 0, item.points_max or 0):
                        item.points_min, item.points_max = lo, hi
                        changed += 1
            if changed:
                game.log(who, f"Changed points on {changed} item(s)")
            flash(f"Updated points on {changed} item(s)." if changed else "No changes.")
        db.session.commit()
        return redirect(url_for("planner.game_settings"))
    items = ([("d", "deadline", d) for d in Deadline.query.order_by(Deadline.due_date)]
             + [("t", "task", t) for t in Task.query.order_by(Task.due_date.is_(None),
                                                             Task.due_date)])
    items = [i for i in items if i[2].school is None or i[2].school.on_list]
    return render_template("game_settings.html", items=items, pot=game.pot_dollars(),
                           start=game.start_date(), paused=game.is_paused(),
                           deadline_points=game.DEADLINE_POINTS,
                           task_points=game.TASK_POINTS)
