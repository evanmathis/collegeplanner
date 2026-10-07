# College Planner

One place for Cian's college applications: the school list, application and music
deadlines, tasks, links, a timeline of what's coming, a log of questions, and the
financial-aid side (aid deadlines, fee waivers, scholarships).

Built with Flask and SQLAlchemy. It uses SQLite on your own computer and MySQL on
DreamHost.

## Pages

- **Home**: what's overdue, what's due in the next 30 days, and progress per school.
- **Timeline**: every deadline, dated task and scholarship deadline by month. Tick items off as they're done.
- **Schools**: Cian's list, plus "Still deciding" (suggested schools, private and out-of-state options, and schools in Spain and Latin America) with a Keep or Remove button on each. Removed schools stay under "Removed" and can be brought back. Only kept schools show on the timeline, tasks and calendar. Each school page has its requirements, extra steps for studying abroad, deadlines, tasks, links and questions.
- **Tasks**: every to-do across all schools.
- **Paying for college**: a short guide to FAFSA / CA Dream Act and Cal Grant, aid deadlines, fee-waiver status per school, and a scholarship tracker.
- **Questions**: log anything you're unsure about and write down the answer when you find it.

## Due dates on your calendar

The **Calendar** page puts every open deadline, dated task and scholarship deadline
on Apple Calendar (or Google/Outlook) as all-day events with reminders at 9am two weeks before, one week before, then daily
until the due date (on a Mac, untick "Remove: Alerts" when subscribing).
There are two ways, with a tradeoff:

- **Subscribe** (recommended): the calendar app re-reads the planner every few hours,
  so changes and finished items stay in sync. It shows up as its own calendar called
  "College Planner" next to Family; no calendar app can merge a subscription into an
  existing calendar. Needs `CALENDAR_TOKEN` set (below) and the site on DreamHost, since
  your phone can't reach a copy running on your computer.
- **Download `college-planner.ics`** and import it into **Family**: the events land in
  Family itself, but it's a one-time copy that won't update.

## Run it on your computer

Needs Python 3.9 or newer.

```bash
git clone https://github.com/evanmathis/collegeplanner.git
cd collegeplanner
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt

python -m flask --app planner seed          # loads the schools and deadlines from data/
python -m flask --app planner run --debug --port 5001   # open http://127.0.0.1:5001
```

Port 5001 because macOS uses port 5000 for AirPlay Receiver; opening
http://127.0.0.1:5000 on a Mac shows a blank page or "403 Forbidden" from AirPlay, not the planner.

Use `python -m flask`, not plain `flask`: if Flask is also installed outside the
virtualenv (for example by Homebrew), plain `flask` can run that copy, which can't see
this app's packages and reports `No module named 'flask_sqlalchemy'` or
`No such command 'seed'`.

The database is `instance/planner.db`. Delete it to start over. Running `seed`
again is safe: it only adds what's missing and never overwrites Cian's own
changes (status, checkmarks, notes).

Run the tests with `pytest`.

## School data

`data/schools.csv` has one row per school (deadlines for the fall 2027 class, checked
2026-10-07), `data/suggestions.csv` and `data/more_schools.csv` (notes in `data/more_schools_notes.md`) have other schools to decide on, and `data/tasks.csv` has the Venice High and application steps (Naviance, Brag Sheet, CaliforniaColleges.edu, letters, UC Personal Insight Questions). `data/README.md`
summarizes the shared deadlines. To update the data, edit the CSVs and run
`python -m flask --app planner seed` again.

## Put it on DreamHost

These steps use DreamHost's Passenger support for Python.

1. **Domain.** In the DreamHost panel, go to *Websites → Manage Websites*, open the
   domain or subdomain (for example `college.yourdomain.com`), and under
   *Additional settings* turn on **Passenger (Ruby/NodeJS/Python apps only)**. Note the
   shell user that owns the site.
2. **MySQL database.** Under *MySQL Databases*, create a database (e.g. `collegeplanner`)
   and a user. Note the hostname (like `mysql.yourdomain.com`), user and password.
3. **Get the code.** SSH in as the site user and clone into the domain folder:
   ```bash
   cd ~/college.yourdomain.com
   git clone https://github.com/evanmathis/collegeplanner.git .
   ```
   (If the folder isn't empty, clone elsewhere and move the files in.)
4. **Virtualenv.** Passenger looks for it at `venv/` in that folder:
   ```bash
   python3 -m venv venv
   venv/bin/pip install -r requirements.txt
   ```
5. **Settings.** `cp .env.example .env`, then edit `.env`:
   - `SECRET_KEY`: any long random string (`python3 -c "import secrets; print(secrets.token_hex(32))"`)
   - `PLANNER_PASSWORD`: the password Cian will type to get in. **Set this**: without it anyone with the URL can see and edit the plan.
   - `DATABASE_URL`: `mysql+pymysql://USER:PASSWORD@mysql.yourdomain.com/collegeplanner?charset=utf8mb4`
   - `CALENDAR_TOKEN`: another long random string. It's the secret part of the calendar
     subscription address (calendar apps can't log in). Change it to cut off old subscriptions.
6. **Create tables and load the schools:**
   ```bash
   set -a; source .env; set +a
   venv/bin/flask --app planner seed
   ```
7. **Start it.** `mkdir -p tmp && touch tmp/restart.txt`, then open the site.
   Turn on HTTPS for the domain in the panel (free Let's Encrypt certificate) so the
   password isn't sent in the clear.

To deploy changes later: `git pull`, `venv/bin/pip install -r requirements.txt` if it
changed, then `touch tmp/restart.txt`.

If the site shows an error, check `~/logs/college.yourdomain.com/http/error.log`.

## Layout

```
planner/            the app (models.py, views.py, seed.py, templates/, static/)
data/               school data loaded by `flask --app planner seed`
passenger_wsgi.py   DreamHost entry point
tests/              pytest tests
```
