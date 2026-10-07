# College Planner

One place for Cian's college applications: the school list, application and music
deadlines, tasks, scholarships, financial aid, a timeline, calendar reminders and a log of
questions. Built with Flask and SQLAlchemy; SQLite on your computer, MySQL on DreamHost.

## Run it on your computer

Needs Python 3.8 or newer.

```bash
git clone https://github.com/evanmathis/collegeplanner.git
cd collegeplanner
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt

python -m flask --app planner seed                      # load schools, tasks, scholarships
python -m flask --app planner run --debug --port 5001   # open http://127.0.0.1:5001
```

- Always use `python -m flask`, not plain `flask`. A `flask` installed elsewhere (for example
  by Homebrew) can't see this app's packages and fails with `No module named
  'flask_sqlalchemy'` or `No such command 'seed'`.
- Port 5001, because macOS uses port 5000 for AirPlay Receiver.
- Next time: `cd collegeplanner && source .venv/bin/activate`, then the `run` line.
- To get updates: `git pull`, `python -m pip install -r requirements-dev.txt`, then
  `python -m flask --app planner seed`.
- The local database is `instance/planner.db`. Delete it to start over.
- Run the tests with `pytest`.

**Seeding is safe to repeat.** It only adds what's missing and fills in blank details. It
never changes Cian's own choices: keep or remove, school status, checkmarks, notes, fee
waivers and scholarship statuses all stay as he set them.

## What's in it

- **Up next** (top of every page): the next open items with colored alerts for overdue,
  due within 3 days and due within 2 weeks. Tick items off right there.
- **Home**: what's overdue, what's due in the next 30 days, and progress per school.
- **Timeline**: every dated deadline, task and interested scholarship, by month.
- **Schools**: Cian's list plus "Still deciding" (more UC/CSU, private, out-of-state and
  Spain/Latin America options) with **Keep** and **Remove** buttons. Removed schools stay
  at the bottom and can be restored. Only kept schools feed the timeline, tasks, alerts and
  calendar. Each school page has requirements, links, deadlines, tasks, questions, "still
  to confirm" notes and extra steps for studying abroad.
- **Tasks**: every to-do, including the Venice High steps (Naviance, Brag Sheet,
  CaliforniaColleges.edu, letters, UC Personal Insight Questions).
- **Scholarships**: researched awards, contests and fee waivers with direct Apply links,
  filtered by type, deadline, school and status. Mark each **Not applied**, **Interested**,
  **Applied** or **Skip**; only Interested ones go on the timeline, alerts and calendar.
  "Opens in a browser only" marks official sites that block automated checks. **Explore
  more** lists free search sites and scam warnings.
- **Paying for college**: FAFSA / CA Dream Act and Cal Grant guide, aid deadlines and
  tasks, and fee-waiver status per school.
- **Questions**: log anything you're unsure about and write down the answer.
- **Calendar**: puts due dates on Apple Calendar, Google or Outlook (below).
- Light and dark mode follow your Mac or phone automatically.

## Due dates on your calendar

Every open deadline, dated task and interested scholarship becomes an all-day event with
reminders at 9am: two weeks before, one week before, then every day until it's due.

- **Subscribe** (recommended, needs the site online): the Calendar page shows a
  subscription link. Your calendar app re-checks it every few hours, so changes and
  finished items stay in sync. It appears as its own "College Planner" calendar next to
  Family; no calendar app can merge a subscription into an existing calendar.
- **Download `college-planner.ics`** and import it into **Family**: the events land in
  Family itself, but it's a one-time copy that won't update.
- **Apple Calendar removes reminders from subscriptions unless you say otherwise.** On a
  Mac, untick **Remove: Alerts** when subscribing (or later under *Get Info*). On iPhone,
  turn off **Remove Alarms**. Google Calendar ignores reminders in subscriptions.

## Put it on DreamHost (Shared Unlimited)

DreamHost no longer offers Passenger, but shared plans still run Python CGI scripts, and
that's how the planner runs there: no extra service and nothing to restart. Each page
takes about a second. The steps use `college.zonelab.app` for the website; use whatever
address you pick.

Your database: **`schoolpicker`**, user **`three5`**, host **`schoolpicker.zonelab.app`**
(never `localhost`).

1. **Website.** In the panel, *Websites → Add Website*, and add `college.zonelab.app` as a
   fully hosted site.
2. **Shell access.** *Websites → SFTP Users & Files*, edit the site's user and make it a
   **Shell user**. Then SSH in: `ssh USER@college.zonelab.app`.
3. **Get the code** into your home folder (outside the website folder, so `.env` is never
   served):
   ```bash
   git clone https://github.com/evanmathis/collegeplanner.git ~/collegeplanner
   cd ~/collegeplanner
   python3 -m venv venv
   venv/bin/pip install -r requirements.txt
   ```
4. **Settings.** `cp .env.example .env && chmod 600 .env`, then `nano .env`:
   ```
   SECRET_KEY=...            # python3 -c "import secrets; print(secrets.token_hex(32))"
   PLANNER_PASSWORD=...      # what Cian types to get in; without it anyone with the URL can edit
   CALENDAR_TOKEN=...        # another long random string; the secret part of the calendar link
   DB_HOST=schoolpicker.zonelab.app
   DB_USER=three5
   DB_PASSWORD='your-mysql-password'
   DB_NAME=schoolpicker
   ```
   Keep the password in single quotes; then no character in it needs escaping. Never put
   the password in chat or in git (`.env` is ignored by git).
5. **Check the database, then load the data:**
   ```bash
   venv/bin/python -m flask --app planner check-db   # explains any problem; never prints the password
   venv/bin/python -m flask --app planner seed
   venv/bin/python -m flask --app planner check-db   # should end with "All good."
   ```
   A new MySQL hostname can take 5-10 minutes to start working.
6. **Turn on the site:**
   ```bash
   cp ~/collegeplanner/deploy/shared/index.cgi ~/collegeplanner/deploy/shared/.htaccess ~/college.zonelab.app/
   chmod 755 ~/college.zonelab.app ~/college.zonelab.app/index.cgi
   ```
7. **HTTPS.** *Websites → Secure Certificates*, add the free Let's Encrypt certificate.
   Then open `https://college.zonelab.app`, log in, and copy the subscription link from the
   Calendar page.

**Updating later:** `cd ~/collegeplanner && git pull`, then
`venv/bin/pip install -r requirements.txt` if it changed and
`venv/bin/python -m flask --app planner seed` if the data changed. No restart needed.

**If something's wrong:**
- Run `check-db` first. It tells you if the host can't be reached, the hostname doesn't
  exist yet, the password is wrong, this computer isn't allowed, or tables are missing.
- "Internal Server Error": look in `~/logs/college.zonelab.app/http/error.log`. Make sure
  `index.cgi` is 755 and the site folder isn't group-writable. If the log says `Option
  ExecCGI not allowed here`, delete the first two lines of `.htaccess`.
- `index.cgi` expects the code in `~/collegeplanner`. If you cloned elsewhere, change
  `APP_DIR` at the top of the copied `index.cgi`.

**Using the DreamHost database from your Mac** (optional): DreamHost only lets its own
servers in by default. In *MySQL Databases*, click `three5` and add your home IP address on
a new line under **Allowable Hosts**, keeping `%.dreamhost.com`. Then put the same `DB_*`
lines in a `.env` in your local copy.

## Other ways to host it

Only needed if CGI on shared hosting stops working or feels too slow:

- **DreamHost Managed VPS** (paid upgrade): faster pages. Do steps 1-5 above, then in
  *Servers & Usage → Manage → Proxy Server* add port `8000` for the site, and keep the app
  running with Gunicorn using DreamHost's "Using linger with Gunicorn" article, with
  `ExecStart=%h/collegeplanner/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:8000 wsgi:app`
  and `WorkingDirectory=%h/collegeplanner`.
- **PythonAnywhere** (paid plan): runs Flask and includes its own MySQL; point the `DB_*`
  lines at that database. Its WSGI file just needs
  `sys.path.insert(0, "/home/YOURNAME/collegeplanner")` and
  `from wsgi import app as application`.
- **Only on your computer**: run it locally as above. Free and private, but the calendar
  subscription and phone access need it online.

## Layout

```
planner/            the app (models.py, views.py, seed.py, checkdb.py, templates/, static/)
data/               school, task and scholarship data loaded by `seed`
deploy/shared/      index.cgi and .htaccess for DreamHost shared hosting
wsgi.py             entry point for Gunicorn (VPS) or PythonAnywhere
tests/              pytest tests
```

To change the data, edit the CSVs in `data/` (see `data/README.md`) and run `seed` again.
