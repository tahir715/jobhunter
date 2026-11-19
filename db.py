import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path("data/jobs.db")


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the jobs table if it doesn't exist."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                organization TEXT,
                url TEXT UNIQUE NOT NULL,
                source TEXT,
                posted_date TEXT,
                deadline TEXT,          -- format: YYYY-MM-DD
                description TEXT,
                first_seen TEXT,
                last_seen TEXT,
                match_score INTEGER,
                applied INTEGER DEFAULT 0
            )
        """)


def save_jobs(jobs, source):
    """Save a list of job dicts. Returns how many were NEW."""
    init_db()
    today = date.today().isoformat()
    new_count = 0
    with get_conn() as conn:
        for j in jobs:
            exists = conn.execute(
                "SELECT id FROM jobs WHERE url = ?", (j["url"],)
            ).fetchone()
            if exists:
                conn.execute(
                    "UPDATE jobs SET last_seen = ?, deadline = COALESCE(?, deadline) WHERE url = ?",
                    (today, j.get("deadline"), j["url"]),
                )
            else:
                conn.execute(
                    """INSERT INTO jobs (title, organization, url, source,
                       posted_date, deadline, description, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        j["title"], j.get("organization"), j["url"], source,
                        j.get("posted_date"), j.get("deadline"),
                        j.get("description"), today, today,
                    ),
                )
                new_count += 1
    return new_count


def get_status(deadline):
    """Open / Closing soon / Closed / Unknown, based on the deadline."""
    if not deadline:
        return "Unknown"
    days_left = (datetime.strptime(deadline, "%Y-%m-%d").date() - date.today()).days
    if days_left < 0:
        return "Closed"
    if days_left <= 3:
        return "Closing soon"
    return "Open"


def get_all_jobs():
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY deadline").fetchall()
    jobs = [dict(r) for r in rows]
    for j in jobs:
        j["status"] = get_status(j["deadline"])
    return jobs


if __name__ == "__main__":
    # Quick test with a fake job
    test = [{
        "title": "AI Engineer (TEST)",
        "organization": "Test Org",
        "url": "https://example.com/job1",
        "deadline": "2026-12-30",
    }]
    print("New jobs saved:", save_jobs(test, "test"))
    for job in get_all_jobs():
        print(job["title"], "|", job["status"], "|", job["deadline"])