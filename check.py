import sqlite3
from enrich import DB, get_text, analyze

conn = sqlite3.connect(DB)
table = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' "
    "AND name NOT LIKE 'sqlite_%' AND name != 'hidden_jobs'").fetchone()[0]
rows = conn.execute(
    f'SELECT title, organization, url FROM "{table}" '
    f'WHERE (deadline IS NULL OR deadline = "") '
    f'AND url LIKE "%.pdf%" ORDER BY RANDOM() LIMIT 8').fetchall()
rows += conn.execute(
    f'SELECT title, organization, url FROM "{table}" '
    f'WHERE (deadline IS NULL OR deadline = "") '
    f'AND url NOT LIKE "%.pdf%" ORDER BY RANDOM() LIMIT 8').fetchall()

for title, org, url in rows:
    text = get_text(url)
    if text is None:
        result = "COULD NOT LOAD"
    elif len(text.strip()) < 50:
        result = "NO TEXT (scanned/image)"
    else:
        posted, deadline = analyze(text)
        result = f"text OK, date found: {deadline}"
    print(f"{org} | {title[:60]}\n   {url[:90]}\n   -> {result}\n")