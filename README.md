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

The planner lives at **https://zonelab.app/collegeplanner/**, with its code in
**`~/zonelab.app/collegeplanner`** (that is, `/home/three5/zonelab.app/collegeplanner`).
DreamHost shared plans run it as a Python CGI script: nothing to start or restart, and each
page takes about a second. The rest of the zonelab.app site is not touched.

That folder is inside the live website, so the planner's `.htaccess` sends every request to
the app. Nothing in the folder (`.env`, `.git`, code, data) can be downloaded; hidden files
get "403 Forbidden" and anything else gets the planner's login page or "Not Found".

Your database: **`schoolpicker`**, user **`three5`**, host **`schoolpicker.zonelab.app`**
(never `localhost`).

**Before you start:** the code must be on the `main` branch on GitHub (merge the pull
request), and your user must be a **Shell user** (*Websites → SFTP Users & Files*).

Run each block over SSH, one at a time, and compare with what it should print.

1. **Look first** (changes nothing):
   ```bash
   ls -la ~/zonelab.app/collegeplanner
   ```
   Should list only `.` and `..` (an empty folder). If it lists anything else, stop: that's
   not ours, so choose another folder name.
2. **Get the code into that folder:**
   ```bash
   rmdir ~/zonelab.app/collegeplanner
   git clone https://github.com/evanmathis/collegeplanner.git ~/zonelab.app/collegeplanner
   cd ~/zonelab.app/collegeplanner
   ls index.cgi .htaccess requirements.txt
   ```
   `rmdir` only removes an empty folder, so it can't delete anything by mistake. The last
   line should print the three file names. (Already cloned to `~/collegeplanner` by
   mistake? Move it instead of cloning again: replace the `git clone` line with
   `mv ~/collegeplanner ~/zonelab.app/collegeplanner`, then run `git pull` inside it.)
3. **Install the app's packages** (takes a minute; ends with "Successfully installed ..."):
   ```bash
   python3 -m venv venv
   venv/bin/pip install -r requirements.txt
   ```
4. **Settings:**
   ```bash
   cp .env.example .env && chmod 600 .env
   python3 -c "import secrets; print(secrets.token_hex(32)); print(secrets.token_hex(16))"
   nano .env
   ```
   Paste the first printed string as `SECRET_KEY` and the second as `CALENDAR_TOKEN`, pick
   a `PLANNER_PASSWORD` for Cian, and type the MySQL password between the single quotes:
   ```
   SECRET_KEY=...
   PLANNER_PASSWORD=...
   CALENDAR_TOKEN=...
   DB_HOST=schoolpicker.zonelab.app
   DB_USER=three5
   DB_PASSWORD='your-mysql-password'
   DB_NAME=schoolpicker
   ```
   Save with Ctrl+O, Enter, Ctrl+X. Never put the password in chat or in git.
5. **Check the database and load the data:**
   ```bash
   venv/bin/python -m flask --app planner check-db
   venv/bin/python -m flask --app planner seed
   venv/bin/python -m flask --app planner check-db
   ```
   The first `check-db` should say "Connected" and then "Missing tables"; that's expected
   before the first seed. The last one should end with "All good." If it can't connect, it
   says why.
6. **Permissions** (DreamHost refuses to run scripts in group-writable folders):
   ```bash
   chmod 755 ~/zonelab.app/collegeplanner index.cgi
   ```
7. **Try it.** Open https://zonelab.app/collegeplanner/ and you should get the planner's
   login page. Then check that nothing private can be downloaded:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://zonelab.app/collegeplanner/.env         # 403
   curl -s -o /dev/null -w "%{http_code}\n" https://zonelab.app/collegeplanner/.git/config  # 403
   curl -s -o /dev/null -w "%{http_code}\n" https://zonelab.app/collegeplanner/data/schools.csv  # 302 (sent to login)
   curl -s -o /dev/null -w "%{http_code}\n" https://zonelab.app/                            # 200, main site as before
   ```
   If zonelab.app doesn't already have HTTPS, add the free Let's Encrypt certificate under
   *Websites → Secure Certificates*. The calendar subscription link (Calendar page) will be
   `https://zonelab.app/collegeplanner/calendar/<your token>.ics`.

**Updating later:**
```bash
cd ~/zonelab.app/collegeplanner && git pull
venv/bin/pip install -r requirements.txt               # only if requirements.txt changed
venv/bin/python -m flask --app planner seed            # only if the data changed
```

**If something's wrong:**
- Run `check-db` first. It says whether the host can't be reached, the hostname doesn't
  exist yet, the password is wrong, this computer isn't allowed, or tables are missing.
- "Internal Server Error": look in `~/logs/zonelab.app/http/error.log`. Make sure step 6
  was done. If the log says `Option ExecCGI not allowed here`, delete the line starting
  with `Options` in `.htaccess` and add `Options -Indexes` in its place.

**Using the DreamHost database from your Mac** (optional): DreamHost only lets its own
servers in by default. In *MySQL Databases*, click `three5` and add your home IP address on
a new line under **Allowable Hosts**, keeping `%.dreamhost.com`. Then put the same `DB_*`
lines in a `.env` in your local copy.

## Other ways to host it

Only needed if CGI on shared hosting stops working or feels too slow:

- **DreamHost Managed VPS** (paid upgrade): faster pages. Clone to `~/collegeplanner` and do steps 3-5 above, then in
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
index.cgi, .htaccess  run the app on shared hosting (DreamHost) and keep the folder private
wsgi.py             entry point for Gunicorn (VPS) or PythonAnywhere
tests/              pytest tests
```

To change the data, edit the CSVs in `data/` (see `data/README.md`) and run `seed` again.
