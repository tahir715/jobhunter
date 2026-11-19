import os, re, secrets, sqlite3, subprocess, sys, threading
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

BASE = Path(__file__).parent
DB = str(BASE / "data" / "jobs.db")
app = FastAPI()
state = {"running": False, "finished": None}

# ---- Admin key (created once, saved in admin_key.txt) ----
KEY_FILE = BASE / "admin_key.txt"
if KEY_FILE.exists():
    ADMIN_KEY = KEY_FILE.read_text().strip()
else:
    ADMIN_KEY = secrets.token_urlsafe(16)
    KEY_FILE.write_text(ADMIN_KEY)


def is_admin(key):
    return bool(key) and secrets.compare_digest(key.encode(), ADMIN_KEY.encode())


def require_admin(x_admin_key: str = Header(default="")):
    if not is_admin(x_admin_key):
        raise HTTPException(status_code=403, detail="Admin only")


JUNK_TITLES = {"view all", "view more", "read more", "more", "jobs", "job", "careers",
    "career", "vacancies", "vacancy", "click here", "apply now", "apply", "recruitment",
    "latest jobs", "all jobs", "home", "details", "download", "advertisement",
    "advertisements", "notice"}
JOB_HINTS = ("vacanc", "job", "recruit", "hiring", "career", "appoint", "position",
    "post of", "posts of", "advertis", "applications", "walk-in", "walk in", "interview",
    "bps", "contract basis", "internship", "fellowship", "faculty", "lecturer", "professor",
    "director", "officer", "engineer", "assistant", "manager", "analyst", "specialist",
    "stenographer", "clerk", "operator")
NOT_JOB = ("advertising", "campaign", "agencies", "portal", "balochistan jobs", "sindh jobs",
    "punjab jobs", "(test)", "audit firm",
    "firm for", "consultancy", "consultant firm", "visit ", "government openings", "tender",
    "proposal", "rfp", "bid", "auction", "quotation", "eoi", "expression of interest",
    "procurement", "notice inviting", "result", "merit list", "admit card", "roll no",
    "syllabus", "date sheet", "datesheet", "scholarship", "admission", "prospectus", "fee ",
    "notification of", "cancel", "corrigendum", "postponed", "extension")

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS hidden_jobs (job_id INTEGER PRIMARY KEY)")
    return c


def is_junk(r):
    t, u = str(r["title"]).strip().lower(), str(r["url"]).strip()
    if t in JUNK_TITLES or len(t) < 10 or t.startswith(("http", "www.")):
        return True
    return u.endswith("#") or u.rstrip("/").lower().endswith(("/jobs", "/careers"))


def looks_like_job(t):
    t = str(t).lower()
    return any(h in t for h in JOB_HINTS) and not any(n in t for n in NOT_JOB)


def date_from_url(url):
    s = str(url).lower()
    try:
        m = re.search(r"(?<!\d)(\d{1,2})[-_. ]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
                      r"[a-z]*[-_. ]?(20\d{2})(?!\d)", s)
        if m:
            return pd.Timestamp(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
        m = re.search(r"(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)", s)
        if m:
            return pd.Timestamp(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = re.search(r"(?<!\d)(\d{1,2})[-_.](\d{1,2})[-_.](20\d{2})(?!\d)", s)
        if m:
            return pd.Timestamp(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = re.search(r"(?<!\d)(20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})(?!\d)", s)
        if m:
            return pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.search(r"(?<!\d)(20(?:1[5-9]|2[0-6]))(?!\d)", s)
        if m and int(m.group(1)) < date.today().year:
            return pd.Timestamp(int(m.group(1)), 12, 31)
    except ValueError:
        pass
    return pd.NaT


def status(r):
    d = r["days_left"]
    if pd.isna(d):
        return "Old (no deadline)" if pd.notna(r["age"]) and r["age"] > 45 else "Date unknown"
    if d < 0:
        return "Expired"
    return "Closing soon" if d <= 7 else "Open"


def load_jobs():
    conn = db()
    t = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE "
                    "'sqlite_%' AND name NOT IN ('hidden_jobs','alerts_sent')", conn)
    df = pd.read_sql(f'SELECT * FROM "{t["name"].iloc[0]}"', conn)
    hidden = set(pd.read_sql("SELECT job_id FROM hidden_jobs", conn)["job_id"])
    conn.close()
    today = pd.Timestamp(date.today())
    df["posted"] = pd.to_datetime(df["posted_date"], errors="coerce")
    df["posted"] = df["posted"].fillna(df["url"].apply(date_from_url))
    df["age"] = (today - df["posted"]).dt.days
    df["closes"] = pd.to_datetime(df["deadline"], errors="coerce")
    df.loc[df["closes"] > today + pd.Timedelta(days=365), "closes"] = pd.NaT
    df["days_left"] = (df["closes"] - today).dt.days
    df["status"] = df.apply(status, axis=1)
    df = df[~df["id"].isin(hidden)]
    df = df[~df.apply(is_junk, axis=1)]
    df = df[df["title"].apply(looks_like_job)].drop_duplicates(subset=["url"])
    df["_k"] = (df["title"].str.lower().str.replace(r"\W+", " ", regex=True).str.strip()
                + "|" + df["organization"].astype(str))
    return df.drop_duplicates(subset=["_k"]), len(hidden)


@app.get("/api/me")
def me(x_admin_key: str = Header(default="")):
    return {"admin": is_admin(x_admin_key)}


@app.get("/api/jobs")
def jobs():
    df, n_hidden = load_jobs()
    out = pd.DataFrame({
        "id": df["id"], "title": df["title"], "org": df["organization"], "url": df["url"],
        "posted": df["posted"].dt.strftime("%Y-%m-%d"),
        "closes": df["closes"].dt.strftime("%Y-%m-%d"),
        "days": df["days_left"], "status": df["status"]}).astype(object)
    out = out.where(out.notna(), None)
    return {"jobs": out.to_dict("records"), "hidden": n_hidden}


class Ids(BaseModel):
    ids: list[int] = []


@app.post("/api/hide", dependencies=[Depends(require_admin)])
def hide(b: Ids):
    c = db()
    c.executemany("INSERT OR IGNORE INTO hidden_jobs (job_id) VALUES (?)", [(i,) for i in b.ids])
    c.commit(); c.close()
    return {"ok": True}


@app.post("/api/unhide", dependencies=[Depends(require_admin)])
def unhide(b: Ids):
    c = db()
    if b.ids:
        c.executemany("DELETE FROM hidden_jobs WHERE job_id=?", [(i,) for i in b.ids])
    else:
        c.execute("DELETE FROM hidden_jobs")
    c.commit(); c.close()
    return {"ok": True}


def _run_update():
    state["running"] = True
    try:
        subprocess.run([sys.executable, str(BASE / "update.py")], cwd=str(BASE))
    finally:
        state["running"] = False
        state["finished"] = datetime.now().isoformat(timespec="seconds")


@app.post("/api/update", dependencies=[Depends(require_admin)])
def update():
    if not state["running"]:
        threading.Thread(target=_run_update, daemon=True).start()
        state["running"] = True
    return state


@app.get("/api/update/status")
def update_status():
    return state


@app.get("/")
def home():
    return FileResponse(BASE / "static" / "index.html")


if __name__ == "__main__":
    import webbrowser
    share = "--share" in sys.argv
    host = "0.0.0.0" if share else "127.0.0.1"
    admin_url = f"http://127.0.0.1:8000/?admin={ADMIN_KEY}"
    print("\n  Job Hunter is starting.")
    print(f"  Admin link (keep private): {admin_url}")
    if share:
        print("  Sharing ON: other devices on your network can open it (read-only for them).\n")
    threading.Timer(1.2, lambda: webbrowser.open(admin_url)).start()
    uvicorn.run(app, host=host, port=8000)