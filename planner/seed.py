"""Load the school data table (data/*.csv) into the database.

Safe to run more than once: schools are matched by name, and deadlines, tasks and
links are only added when an identical one isn't already there. Cian's own changes
(status, including keep / remove choices, fee waiver, notes, done checkboxes) are
never overwritten.
"""
import csv
import os
import re
from datetime import date

import click

from . import db
from .models import Deadline, Link, School, Task

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Deadlines that apply to every school (from data/README.md).
SHARED_DEADLINES = [
    ("FAFSA or CA Dream Act + Cal Grant GPA Verification due", "2027-03-02", "Financial aid",
     "Also the campus financial-aid priority date for every UC and CSU on the list."),
    ("Commit: Statement of Intent to Register", "2027-05-01", "Application", ""),
]
SHARED_TASKS = [
    ("Submit the FAFSA or CA Dream Act Application (opened Oct 1)", "2027-03-02", "Financial aid"),
    ("Confirm the high school is sending the Cal Grant GPA Verification", "2027-03-02",
     "Financial aid"),
    ("Check the fee waiver inside the UC Application (covers up to 4 campuses)", "2026-11-30",
     "Financial aid"),
    ("Check the fee waiver inside Cal State Apply", "2026-11-30", "Financial aid"),
]

DATE_RE = re.compile(r"(?:(\d{4})-)?(\d{2})-(\d{2})")


def parse_dates(text):
    """Find dates like 2027-02-06 and short follow-ons like '02-13' that reuse the year."""
    found, year = [], None
    for m in DATE_RE.finditer(text or ""):
        if m.group(1):
            year = int(m.group(1))
        if year is None:
            continue
        try:
            found.append(date(year, int(m.group(2)), int(m.group(3))))
        except ValueError:
            continue
    return found


def has_words(text):
    """True when text says more than just dates (e.g. 'Music application 2027-01-15')."""
    return bool(re.search(r"[A-Za-z]{3,}", DATE_RE.sub("", text)))


def add_deadline(school, title, due, kind, notes=""):
    exists = Deadline.query.filter_by(school_id=school.id if school else None,
                                      title=title, due_date=due).first()
    if not exists:
        db.session.add(Deadline(school=school, title=title, due_date=due, kind=kind,
                                notes=notes))
        return 1
    return 0


def add_task(school, title, due, category):
    exists = Task.query.filter_by(school_id=school.id if school else None, title=title).first()
    if not exists:
        db.session.add(Task(school=school, title=title, category=category,
                            due_date=date.fromisoformat(due) if due else None))
        return 1
    return 0


def deadlines_from_column(school, text, kind, default_title, label=False):
    """One deadline per ';'-separated part that has a date.

    With label=True a short word next to the date names the deadline,
    e.g. "EA 2026-11-01" becomes "Application due (EA)".
    """
    added = 0
    for part in (text or "").split(";"):
        dates = parse_dates(part)
        if not dates:
            continue
        title = default_title
        words = re.sub(r"[()]", "", DATE_RE.sub("", part)).strip(" ,:")
        if label and words and len(words) <= 20:
            title += f" ({words})"
        elif len(dates) > 1:
            title += " (pick a date)"
        notes = part.strip() if has_words(part) or len(dates) > 1 else ""
        added += add_deadline(school, title, dates[0], kind, notes)
    return added


def get_or_create_school(name, **defaults):
    school = School.query.filter_by(name=name).first()
    created = school is None
    if created:
        school = School(name=name, **defaults)
        db.session.add(school)
        db.session.flush()
    return school, created


def import_schools(path):
    stats = dict(schools=0, deadlines=0, tasks=0, links=0)
    shared_aid = date.fromisoformat(SHARED_DEADLINES[0][1])
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            school, created = get_or_create_school(row["school"].strip(), status="Applying")
            stats["schools"] += created
            school.system = row["system"]
            school.degree = row["degree_for_composition"]
            school.app_platform = row["app_platform"]
            school.music_requirement = row["music_requirement"]
            school.program_link = row["program_link"]
            school.data_status = row["status"]
            if not school.notes:
                school.notes = row["notes"]

            for due in parse_dates(row["app_deadline"])[:1]:
                stats["deadlines"] += add_deadline(
                    school, f"Submit {row['app_platform'] or 'application'}", due, "Application")
            stats["deadlines"] += deadlines_from_column(
                school, row["music_deadline"], "Music", "Music application / portfolio due")
            stats["deadlines"] += deadlines_from_column(
                school, row["audition_or_interview_dates"], "Music", "Audition / interview")
            for due in parse_dates(row["aid_priority_deadline"])[:1]:
                if due != shared_aid:  # the shared date is added once, not per school
                    stats["deadlines"] += add_deadline(
                        school, "Financial aid priority date", due, "Financial aid")

            if row["program_link"] and not Link.query.filter_by(
                    school_id=school.id, url=row["program_link"]).first():
                db.session.add(Link(school=school, label="Music program / admissions page",
                                    url=row["program_link"]))
                stats["links"] += 1
            if row["status"].strip().lower() != "verified":
                stats["tasks"] += add_task(
                    school, "Confirm music admission requirements with the department",
                    None, "Music")

    for title, due, kind, notes in SHARED_DEADLINES:
        stats["deadlines"] += add_deadline(None, title, date.fromisoformat(due), kind, notes)
    for title, due, category in SHARED_TASKS:
        stats["tasks"] += add_task(None, title, due, category)
    db.session.commit()
    return stats


def import_suggestions(path):
    added = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["school"].strip()
            if row["state"] != "CA":
                system = "Out of state"
            elif name.startswith("UC "):
                system = "UC"
            else:
                system = "CSU"
            _, created = get_or_create_school(name, status="Considering", system=system,
                                              notes=row["why"])
            added += created
    # Earlier versions loaded these as "Idea"; that was the seed's default, not Cian's choice.
    School.query.filter_by(status="Idea").update({"status": "Considering"})
    db.session.commit()
    return added


def import_more_schools(path):
    """US private, out-of-state and abroad options (more_schools.csv), all as "Considering"
    until Cian keeps or removes them."""
    stats = dict(schools=0, deadlines=0, links=0)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            country, city = row["country"].strip(), row["city"].strip()
            if not country.startswith("USA"):
                system = "Abroad"
            elif city.endswith(" CA"):
                system = "California private" if row["type"] == "private" else "Other"
            else:
                system = "Out of state"
            school, created = get_or_create_school(row["school"].strip(), status="Considering")
            stats["schools"] += created
            school.system = system
            school.country, school.city = country, city
            school.school_type = row["type"]
            school.degree = row["degree_for_composition"]
            school.app_platform = row["app_route"]
            school.app_deadline_note = row["app_deadline"]
            school.music_requirement = row["music_requirement"]
            school.entry_term = row["entry_for_fall_2027"]
            school.language = row["language"]
            school.cost = row["rough_cost_usd_per_year"]
            school.us_aid = row["us_aid"]
            school.abroad_steps = row["what_cian_needs_abroad"]
            school.program_link = row["program_link"]
            school.data_status = row["confidence"]
            if not school.notes:
                school.notes = row["why"]

            stats["deadlines"] += deadlines_from_column(
                school, row["app_deadline"], "Application", "Application due", label=True)
            stats["deadlines"] += deadlines_from_column(
                school, row["music_requirement"], "Music", "Audition / exam")
            if row["program_link"] and not Link.query.filter_by(
                    school_id=school.id, url=row["program_link"]).first():
                db.session.add(Link(school=school, label="Program / admissions page",
                                    url=row["program_link"]))
                stats["links"] += 1
    db.session.commit()
    return stats


LINK_LABELS = [("program_link", "Composition program page"),
               ("admissions_link", "Music admissions / audition / portfolio"),
               ("aid_link", "Financial aid / net price calculator")]


def add_link(school, label, url):
    if url and not Link.query.filter_by(school_id=school.id, url=url).first():
        db.session.add(Link(school=school, label=label, url=url))
        return 1
    return 0


def import_school_details(path):
    """Extra facts and links for US schools (school_details.csv), matched by name.

    Fills in what the other files leave blank; it never changes status, notes or
    anything Cian has edited, and only adds links that aren't there yet.
    """
    stats = dict(schools=0, links=0, deadlines=0)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            school = School.query.filter_by(name=row["school"].strip()).first()
            if not school:
                continue
            stats["schools"] += 1

            def fill(attr, value, overwrite=False):
                value = (value or "").strip()
                if value and (overwrite or not getattr(school, attr)):
                    setattr(school, attr, value)

            place = " ".join(p for p in (row.get("city", ""), row.get("state", "")) if p)
            fill("city", place)
            fill("country", "USA" if place else "")
            fill("school_type", row.get("type"))
            fill("degree", row.get("degree_for_composition"))
            new_program = (row.get("program_link") or "").strip()
            if new_program and school.program_link and new_program != school.program_link:
                # The imported page moved; repoint the link we created for it.
                Link.query.filter_by(school_id=school.id, url=school.program_link).update(
                    {"url": new_program, "label": "Composition program page"})
            fill("program_link", new_program, overwrite=True)
            fill("app_platform", row.get("app_route"))
            fill("app_deadline_note", row.get("app_deadline"))
            fill("music_requirement", row.get("music_requirement"))
            fill("entry_term", row.get("entry"))
            fill("language", row.get("language"))
            fill("cost", row.get("cost"))
            fill("us_aid", row.get("us_aid"))
            fill("to_confirm", row.get("unconfirmed"), overwrite=True)
            if row.get("confidence") and school.status in ("Considering", "Idea"):
                fill("data_status", row["confidence"], overwrite=True)

            for key, label in LINK_LABELS:
                stats["links"] += add_link(school, label, (row.get(key) or "").strip())
            # Dated deadlines only for schools that don't have any yet (the suggestions),
            # so the main list's checked deadlines aren't duplicated.
            if not school.deadlines:
                stats["deadlines"] += deadlines_from_column(
                    school, row.get("app_deadline"), "Application", "Application due",
                    label=True)
                stats["deadlines"] += deadlines_from_column(
                    school, row.get("music_deadline"), "Music", "Music application / portfolio due")
    db.session.commit()
    return stats


TASK_CATEGORY_MAP = {"school": "High school", "application": "Application"}
APPLIES_TO_LABELS = {"UC": "UC Application", "CSU": "Cal State Apply", "UC;CSU": "UC and Cal State",
                     "all": "All schools", "as needed": "Only if a school asks"}


def import_tasks(path):
    """High school and application steps (tasks.csv); not tied to one school."""
    added = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            title = row["task"].strip()
            if Task.query.filter_by(school_id=None, title=title).first():
                continue
            dates = parse_dates(row["due"])
            notes = [row["how"].strip()]
            if not dates and row["due"].strip():
                notes.append("When: " + row["due"].strip())
            applies = row["applies_to"].strip()
            notes.append("For: " + APPLIES_TO_LABELS.get(applies, applies))
            if row.get("source"):
                notes.append("Source: " + row["source"].strip())
            db.session.add(Task(title=title, due_date=dates[0] if dates else None,
                                category=TASK_CATEGORY_MAP.get(row["category"].strip(), "General"),
                                notes="\n".join(n for n in notes if n)))
            added += 1
    db.session.commit()
    return added


def register_cli(app):
    @app.cli.command("seed")
    @click.option("--data-dir", default=DATA_DIR, show_default=True,
                  help="Folder holding schools.csv, suggestions.csv, more_schools.csv, tasks.csv.")
    def seed_command(data_dir):
        """Import the school list, deadlines, suggestions and tasks."""
        stats = import_schools(os.path.join(data_dir, "schools.csv"))
        click.echo("Added {schools} schools, {deadlines} deadlines, {tasks} tasks, "
                   "{links} links.".format(**stats))
        suggestions = os.path.join(data_dir, "suggestions.csv")
        if os.path.exists(suggestions):
            click.echo(f"Added {import_suggestions(suggestions)} suggested schools.")
        more = os.path.join(data_dir, "more_schools.csv")
        if os.path.exists(more):
            stats = import_more_schools(more)
            click.echo("Added {schools} more schools (private, out of state, abroad), "
                       "{deadlines} deadlines, {links} links.".format(**stats))
        details = os.path.join(data_dir, "school_details.csv")
        if os.path.exists(details):
            stats = import_school_details(details)
            click.echo("Filled in details for {schools} US schools: {links} links, "
                       "{deadlines} deadlines.".format(**stats))
        tasks = os.path.join(data_dir, "tasks.csv")
        if os.path.exists(tasks):
            click.echo(f"Added {import_tasks(tasks)} high school and application tasks.")
