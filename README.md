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

## Put it online

There are three ways to run the planner, depending on the hosting:

| What your hosting has | Use |
|---|---|
| DreamHost shared hosting, or any Apache host that runs `.cgi` scripts, and no "Python app" tool | **Shared hosting with CGI** (below) |
| A control panel with **Setup Python App**, **Python Selector** or a **Python** app manager (cPanel, CloudLinux, Plesk) | **Shared hosting with a Python app tool** (below) |
| A DreamHost Managed VPS or Dedicated server | **Option A** |

DreamHost's own panel (panel.dreamhost.com) has no Python app tool any more (its knowledge
base lists Passenger as "Not supported on DreamHost servers"), but its shared servers still
run Python CGI scripts, so use the CGI route there.

The steps use `college.zonelab.app` for the website and the MySQL database `schoolpicker`
(user `three5`, hostname `schoolpicker.zonelab.app`).

### Setting up the code and database (every route)

1. **SSH.** Make sure the site's user has shell (SSH) access. On DreamHost: *Websites →
   SFTP Users & Files*, edit the user, choose *Shell user*.
2. **Get the code** into your home folder, outside the website folder so `.env` is never
   served:
   ```bash
   git clone https://github.com/evanmathis/collegeplanner.git ~/collegeplanner
   cd ~/collegeplanner
   python3 --version            # needs 3.9 or newer
   python3 -m venv venv
   venv/bin/pip install -r requirements.txt
   ```
   (With a Python app tool, let the tool make the virtualenv instead; see that section.)
3. **Settings.** `cp .env.example .env`, `chmod 600 .env`, then edit it (`nano .env`):
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
   `/` or `#` in it. The website and every `flask` command read `.env` on their own.
4. **Check the connection, then load the data:**
   ```bash
   venv/bin/python -m flask --app planner check-db   # says what's wrong, never prints the password
   venv/bin/python -m flask --app planner seed       # creates the tables, loads schools and scholarships
   venv/bin/python -m flask --app planner check-db   # should end with "All good."
   ```
   Use the hostname, never `localhost`. A new MySQL hostname can take 5-10 minutes to start
   working.

### Shared hosting with CGI (DreamHost shared)

1. Copy the two files from `deploy/shared/` into the website's folder (on DreamHost, the
   folder named after the site in your home folder):
   ```bash
   cp ~/collegeplanner/deploy/shared/index.cgi ~/collegeplanner/deploy/shared/.htaccess ~/college.zonelab.app/
   chmod 755 ~/college.zonelab.app ~/college.zonelab.app/index.cgi
   ```
   `index.cgi` runs the app from `~/collegeplanner` with its `venv`. If you cloned
   somewhere else, change `APP_DIR` at the top of `index.cgi`.
2. Open the site. That's it: there is nothing to start or restart, because each page
   request runs the script fresh (so each page takes about a second).
3. **HTTPS.** Add a free Let's Encrypt certificate (*Websites → Secure Certificates* on
   DreamHost), then open the Calendar page over `https://` to copy the subscription address.

To deploy changes later: `cd ~/collegeplanner && git pull`, then
`venv/bin/pip install -r requirements.txt` if it changed and
`venv/bin/python -m flask --app planner seed` if the data changed.

If a page shows "Internal Server Error", check the site's error log
(`~/logs/college.zonelab.app/http/error.log` on DreamHost) and make sure `index.cgi` is 755
with Unix line endings and the folder isn't group-writable.

### Shared hosting with a Python app tool (cPanel and similar)

1. Do steps 1-2 of the setup above, but skip making `venv`.
2. In the control panel, open **Setup Python App** (or *Python Selector*), click
   **Create Application**, and set: Python version 3.9 or newer, *Application root*
   `collegeplanner`, *Application URL* your site, *Application startup file*
   `passenger_wsgi.py`, *Application entry point* `application`. Click **Create**.
   (If it replaced `passenger_wsgi.py`, run `git checkout passenger_wsgi.py`.)
3. Copy the "Enter to the virtual environment" command it shows at the top, run it over
   SSH, then `cd ~/collegeplanner && pip install -r requirements.txt`.
4. Do steps 3-4 of the setup above, using `python` instead of `venv/bin/python`.
5. Click **Restart** in the Python app page, then open the site. Turn on HTTPS in the panel
   (*SSL/TLS Status* or *Let's Encrypt*).

To deploy changes later: `git pull`, `pip install -r requirements.txt` if it changed, then
**Restart**.

### Option A: DreamHost Managed VPS

1. **Move the site onto the VPS.** In the panel, open *Websites*, add or open
   `college.zonelab.app` (fully hosted), and pick the VPS as its server.
2. **Proxy.** Open *Servers & Usage*, click **Manage** next to the VPS, scroll to
   **Proxy Server**, choose `college.zonelab.app`, leave the directory blank, enter port
   `8000`, and click **Add Proxy**.
3. Do steps 1-4 of the setup above.
4. **Keep it running** (DreamHost's "Using linger with Gunicorn" steps):
   ```bash
   loginctl enable-linger
   mkdir -p ~/.config/systemd/user
   cat > ~/.config/systemd/user/planner.service <<'UNIT'
   [Unit]
   Description=College Planner
   After=network.target

   [Service]
   WorkingDirectory=%h/collegeplanner
   ExecStart=%h/collegeplanner/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:8000 wsgi:app
   Restart=on-failure

   [Install]
   WantedBy=default.target
   UNIT
   systemctl --user enable --now planner
   systemctl --user status planner
   ```
5. **HTTPS.** Add a free Let's Encrypt certificate for the site (*Websites → Secure
   Certificates*). The proxy uses it automatically. Then open the Calendar page over
   `https://` to copy the subscription address.

To deploy changes later: `git pull`, `venv/bin/pip install -r requirements.txt` if it
changed, `venv/bin/python -m flask --app planner seed` if the data changed, then
`systemctl --user restart planner`. Logs: `journalctl --user -u planner`.

### Option B: PythonAnywhere (no VPS)

PythonAnywhere runs Flask apps on its paid plans, which include a MySQL database. Free
accounts can't connect to outside databases. Two ways to use it:

- **Simplest:** use PythonAnywhere's own MySQL. On its *Databases* tab, create a database,
  then put its host, user, password and name in the `DB_*` lines of `.env`.
- **Keep the DreamHost database:** PythonAnywhere's addresses aren't fixed, so DreamHost's
  *Allowable Hosts* would need `%` (any address, protected only by the password). Not
  recommended.

Setup: clone the repo in a PythonAnywhere Bash console, make the virtualenv and `.env` as
in the setup above, add a *Manual configuration* web app pointed at the virtualenv, and make its
WSGI file:
```python
import sys
sys.path.insert(0, "/home/YOURNAME/collegeplanner")
from wsgi import app as application
```

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
wsgi.py             entry point for Gunicorn (VPS) and PythonAnywhere
passenger_wsgi.py   entry point for control-panel Python apps (cPanel and similar)
deploy/shared/      index.cgi and .htaccess for CGI shared hosting
tests/              pytest tests
```
