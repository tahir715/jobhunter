import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from server import load_jobs

BASE = Path(__file__).parent
OUT = BASE / "site"
OUT.mkdir(exist_ok=True)

df, hidden = load_jobs()
out = pd.DataFrame({
    "id": df["id"], "title": df["title"], "org": df["organization"], "url": df["url"],
    "posted": df["posted"].dt.strftime("%Y-%m-%d"),
    "closes": df["closes"].dt.strftime("%Y-%m-%d"),
    "days": df["days_left"], "status": df["status"]})

payload = {
    "jobs": json.loads(out.to_json(orient="records", force_ascii=False)),
    "hidden": hidden,
    "generated": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
}
(OUT / "jobs.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

# Build the static page from your dashboard: read jobs.json instead of the API
html = (BASE / "static" / "index.html").read_text(encoding="utf-8")
html = html.replace('fetch("/api/jobs")', 'fetch("jobs.json?v="+Date.now())')
html = html.replace('"Updated "+new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})',
                    '"Data updated "+(d.generated||"")')
html = html.replace("load();poll();setInterval(load,60000);", "load();setInterval(load,300000);")
(OUT / "index.html").write_text(html, encoding="utf-8")
print(f"Exported {len(payload['jobs'])} jobs to site/")