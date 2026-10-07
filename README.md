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
- **Scholarships**: 35 researched scholarships, contests and fee waivers with direct apply links, filterable by type, deadline, school and status. Cian marks each as Not applied, Interested, Applied or Skip; only Interested ones go on the timeline, Up next and the calendar. "Opens in a browser only" marks sites that block automated checks. Search sites and scam warnings sit under Explore more.
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
2026-10-07), `data/suggestions.csv` and `data/more_schools.csv` (notes in `data/more_schools_notes.md`) have other schools to decide on, and `data/tasks.csv` has the Venice High and application steps (Naviance, Brag Sheet, CaliforniaColleges.edu, letters, UC Personal Insight Questions), and `data/scholarships.csv` has the scholarships (checked 2026-10-07). `data/README.md`
summarizes the shared deadlines. To update the data, edit the CSVs and run
`python -m flask --app planner seed` again.

## Put it on DreamHost

These steps use DreamHost's Passenger support for Python and the MySQL database
`schoolpicker` (user `three5`, hostname `schoolpicker.zonelab.app`). The examples use
`college.zonelab.app` for the website; use whatever site name you pick.

1. **Website with Passenger.** In the DreamHost panel, go to *Websites*, add or open the
   site (for example `college.zonelab.app`), and in its settings turn on
   **Passenger (Ruby/NodeJS/Python apps only)**. The web directory must end in `/public`
   (for example `/home/USER/college.zonelab.app/public`). Note the SFTP/SSH user that owns
   the site and make sure that user has shell (SSH) access.
2. **Get the code.** SSH in as that user and put the code in the site folder (one level
   above `public`). The folder isn't empty, so fetch into it rather than cloning:
   ```bash
   cd ~/college.zonelab.app
   git init
   git remote add origin https://github.com/evanmathis/collegeplanner.git
   git fetch origin
   git checkout -t origin/main
   ```
3. **Virtualenv.** Passenger's entry point (`passenger_wsgi.py`) looks for it at `venv/`:
   ```bash
   python3 --version            # needs 3.9 or newer
   python3 -m venv venv
   venv/bin/pip install -r requirements.txt
   ```
4. **Settings.** `cp .env.example .env`, `chmod 600 .env`, then edit it (`nano .env`):
   ```
   SECRET_KEY=...            # python3 -c "import secrets; print(secrets.token_hex(32))"
   PLANNER_PASSWORD=...      # what Cian types to get in; without it anyone with the URL can edit
   CALENDAR_TOKEN=...        # another long random string; secret part of the calendar feed URL
   DB_HOST=schoolpicker.zonelab.app
   DB_USER=three5
   DB_PASSWORD='your MySQL password'
   DB_NAME=schoolpicker
   ```
   Put the password in single quotes. It never needs escaping this way, even with `@`, `:`,
   `/` or `#` in it. (A single `DATABASE_URL=mysql+pymysql://...` line still works too, but
   then special characters in the password must be URL-encoded.) The website and every
   `flask` command read `.env` on their own.
5. **Check the connection, then load the data:**
   ```bash
   venv/bin/python -m flask --app planner check-db   # says what's wrong, never prints the password
   venv/bin/python -m flask --app planner seed       # creates the tables, loads schools and scholarships
   venv/bin/python -m flask --app planner check-db   # should end with "All good."
   ```
   Use the hostname, never `localhost`. A new MySQL hostname can take 5-10 minutes to start
   working.
6. **Start it.** `mkdir -p tmp && touch tmp/restart.txt`, then open the site.
7. **HTTPS.** In the panel, add a free Let's Encrypt certificate for the site (*Websites →
   Secure Certificates*). Then open the Calendar page over `https://` to copy the
   subscription address.

To deploy changes later: `git pull`, `venv/bin/pip install -r requirements.txt` if it
changed, `venv/bin/python -m flask --app planner seed` if the data changed, then
`touch tmp/restart.txt`.

If the site shows an error, check `~/logs/college.zonelab.app/http/error.log`, and run
`check-db` first.

### Reaching the database from your own computer (optional)

DreamHost only lets its own servers into MySQL by default (the user's *Allowable Hosts* is
`%.dreamhost.com`). To run `check-db` or `seed` from your Mac against the DreamHost
database, open *MySQL Databases* in the panel, click `three5`, and add your home IP address
(search "what is my IP") on a new line under **Allowable Hosts**. Keep `%.dreamhost.com`, or
the website loses access. Then put the same `DB_*` lines in a `.env` on your Mac. If
`check-db` reports error 1130, 1045 or 2003 from home, this setting is the usual cause.

## Layout

```
planner/            the app (models.py, views.py, seed.py, templates/, static/)
data/               school data loaded by `flask --app planner seed`
passenger_wsgi.py   DreamHost entry point
tests/              pytest tests
```
