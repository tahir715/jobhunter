import io
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import requests
import urllib3
from bs4 import BeautifulSoup
from dateutil import parser as dparser
from pypdf import PdfReader

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB = "data/jobs.db"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}
CLOSE_KEYS = (
    "last date", "closing date", "close date", "closes on", "deadline",
    "on or before", "not later than", "no later than", "last day",
    "submission date", "date of submission", "submitted by", "received by",
    "reach by", "must reach", "up to", "upto", "until", "till", "before",
    "closing", "last date of receipt", "due date", "apply by", "apply before",
)
M = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
SEP = r"[\s\-/.,]*"
DATE_RE = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?{SEP}(?:of{SEP})?{M}{SEP}\d{{2,4}}\b"
    rf"|\b{M}{SEP}\d{{1,2}}(?:st|nd|rd|th)?{SEP}\d{{4}}\b"
    rf"|\b\d{{1,2}}[-/.]\d{{1,2}}[-/.]\d{{2,4}}\b"
    rf"|\b\d{{4}}[-/.]\d{{1,2}}[-/.]\d{{1,2}}\b", re.I)


def to_date(s):
    s = re.sub(r"(?<=\d)(st|nd|rd|th)", "", s, flags=re.I)
    s = re.sub(r"\bof\b", " ", s, flags=re.I)
    try:
        d = dparser.parse(s, dayfirst=True, fuzzy=True).date()
    except Exception:
        return None
    return d if date(2020, 1, 1) <= d <= date(2028, 12, 31) else None


def dates_after(text, keys, span=140):
    out, low = [], text.lower()
    for k in keys:
        for m in re.finditer(re.escape(k), low):
            dm = DATE_RE.search(text[m.end(): m.end() + span])
            if dm:
                d = to_date(dm.group())
                if d:
                    out.append(d)
    return out


def analyze(text):
    text = re.sub(r"\s+", " ", text)
    closes = dates_after(text, CLOSE_KEYS)
    # Prefer upcoming dates; otherwise take the latest one found
    future = [d for d in closes if d >= date.today()]
    deadline = min(future) if future else (max(closes) if closes else None)
    posted = None
    for m in DATE_RE.finditer(text[:1200]):
        d = to_date(m.group())
        if d and d <= date.today():
            posted = d
            break
    if posted and deadline and posted >= deadline:
        posted = None
    return posted, deadline


def get_text(url):
    r = None
    for verify in (True, False):
        try:
            r = requests.get(url, headers=HEADERS, timeout=25, verify=verify)
            r.raise_for_status()
            break
        except Exception:
            r = None
    if r is None:
        return None
    ctype = r.headers.get("content-type", "").lower()
    if "pdf" in ctype or url.lower().split("?")[0].endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(r.content))
            return " ".join((p.extract_text() or "") for p in reader.pages[:5])
        except Exception:
            return None
    if "html" in ctype or "text" in ctype:
        return BeautifulSoup(r.text, "html.parser").get_text(" ")[:30000]
    return None


def work(row):
    job_id, url, title = row
    text = get_text(url)
    if text is None:
        return job_id, None, None, False
    posted, deadline = analyze((title or "") + " . " + text)
    return job_id, posted, deadline, True


if __name__ == "__main__":
    conn = sqlite3.connect(DB)
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name != 'hidden_jobs'").fetchone()[0]
    cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{table}")')]
    if "date_checked" not in cols:
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN date_checked TEXT')
    # Re-check everything that still has no closing date
    conn.execute(f'UPDATE "{table}" SET date_checked = NULL '
                 f'WHERE deadline IS NULL OR deadline = ""')
    conn.commit()

    rows = conn.execute(
        f'SELECT id, url, title FROM "{table}" WHERE date_checked IS NULL'
    ).fetchall()

    todo = []
    for job_id, url, title in rows:
        u = (url or "").lower()
        if (not url or len(title or "") < 10 or u.endswith("#")
                or u.split("?")[0].endswith((".jpg", ".jpeg", ".png", ".gif"))):
            conn.execute(f'UPDATE "{table}" SET date_checked="skip" WHERE id=?', (job_id,))
        else:
            todo.append((job_id, url, title))
    conn.commit()
    print(f"Checking {len(todo)} job pages... (a few minutes)")

    found = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for job_id, posted, deadline, ok in ex.map(work, todo):
            if not ok:
                continue
            conn.execute(
                f'UPDATE "{table}" SET posted_date = COALESCE(posted_date, ?), '
                f'deadline = COALESCE(?, deadline), date_checked = ? WHERE id = ?',
                (posted.isoformat() if posted else None,
                 deadline.isoformat() if deadline else None,
                 date.today().isoformat(), job_id))
            if deadline:
                found += 1
    conn.commit()
    print(f"Done. Closing date found for {found} of {len(todo)} jobs.")