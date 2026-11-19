import html
import re
import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Job Hunter", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
.hero {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    padding: 26px 32px; border-radius: 16px; margin-bottom: 18px; color: #fff;
}
.hero h1 {margin: 0; font-size: 2rem; color: #fff; padding: 0;}
.hero p {margin: 4px 0 0 0; opacity: .9; font-size: .95rem;}
[data-testid="stMetric"] {
    background: rgba(128,128,128,.08); border: 1px solid rgba(128,128,128,.22);
    padding: 14px 18px; border-radius: 12px;
}
.job-title {font-size: 1.02rem; font-weight: 650; line-height: 1.35;}
.job-org {opacity: .7; font-size: .88rem; margin-top: 2px;}
.job-when {font-size: .9rem; line-height: 1.5;}
.job-when small {opacity: .65;}
.badge {
    display: inline-block; padding: 3px 12px; border-radius: 999px;
    font-size: .76rem; font-weight: 700; letter-spacing: .02em;
}
.b-soon {background: #fee2e2; color: #b91c1c;}
.b-open {background: #dcfce7; color: #15803d;}
.b-unknown {background: #fef3c7; color: #a16207;}
.b-old {background: #e5e7eb; color: #4b5563;}
</style>
""", unsafe_allow_html=True)

st.markdown(
    f'<div class="hero"><h1>🎯 Job Hunter</h1>'
    f'<p>Federal government jobs · closing soonest first · {date.today():%A, %d %B %Y}</p></div>',
    unsafe_allow_html=True)

# ---------------- Data ----------------
DB = "data/jobs.db"
conn = sqlite3.connect(DB)
conn.execute("CREATE TABLE IF NOT EXISTS hidden_jobs (job_id INTEGER PRIMARY KEY)")
conn.commit()

tables = pd.read_sql(
    "SELECT name FROM sqlite_master WHERE type='table' "
    "AND name NOT LIKE 'sqlite_%' "
    "AND name NOT IN ('hidden_jobs','alerts_sent')", conn)
if tables.empty:
    st.warning("No jobs table found in data/jobs.db")
    st.stop()

df = pd.read_sql(f'SELECT * FROM "{tables["name"].iloc[0]}"', conn)
hidden_ids = set(pd.read_sql("SELECT job_id FROM hidden_jobs", conn)["job_id"])

JUNK_TITLES = {
    "view all", "view more", "read more", "more", "jobs", "job", "careers",
    "career", "vacancies", "vacancy", "click here", "apply now", "apply",
    "recruitment", "latest jobs", "all jobs", "home", "details", "download",
    "advertisement", "advertisements", "notice",
}
JOB_HINTS = ("vacanc", "job", "recruit", "hiring", "career", "appoint",
             "position", "post of", "posts of", "advertis", "applications",
             "walk-in", "walk in", "interview", "bps", "contract basis",
             "internship", "fellowship", "faculty", "lecturer", "professor",
             "director", "officer", "engineer", "assistant", "manager",
             "analyst", "specialist", "stenographer", "clerk", "operator")
NOT_JOB = ("portal", "balochistan jobs", "sindh jobs", "punjab jobs", "(test)",
           "audit firm", "firm for", "consultancy", "consultant firm",
           "visit ", "government openings", "tender", "proposal", "rfp",
           "bid", "auction", "quotation", "eoi", "expression of interest",
           "procurement", "notice inviting", "result", "merit list",
           "admit card", "roll no", "syllabus", "date sheet", "datesheet",
           "scholarship", "admission", "prospectus", "fee ", "notification of",
           "cancel", "corrigendum", "postponed", "extension")


def is_junk(row):
    title = str(row["title"]).strip().lower()
    url = str(row["url"]).strip()
    if title in JUNK_TITLES or len(title) < 10:
        return True
    if title.startswith(("http", "www.")):
        return True
    return url.endswith("#") or url.rstrip("/").lower().endswith(("/jobs", "/careers"))


def looks_like_job(title):
    t = str(title).lower()
    return any(h in t for h in JOB_HINTS) and not any(n in t for n in NOT_JOB)


# ---------------- Dates ----------------
today = pd.Timestamp(date.today())
df["posted"] = pd.to_datetime(df["posted_date"], errors="coerce")


def date_from_url(url):
    """Finds ddmmyyyy in file names like adv_28072026.pdf"""
    m = re.search(r"(?<!\d)(\d{2})(\d{2})(20\d{2})(?!\d)", str(url))
    if m:
        try:
            return pd.Timestamp(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return pd.NaT
    return pd.NaT


df["posted"] = df["posted"].fillna(df["url"].apply(date_from_url))
df["age"] = (today - df["posted"]).dt.days
df["closes"] = pd.to_datetime(df["deadline"], errors="coerce")
df.loc[df["closes"] > today + pd.Timedelta(days=365), "closes"] = pd.NaT
df["days_left"] = (df["closes"] - today).dt.days


def status(row):
    d = row["days_left"]
    if pd.isna(d):
        if pd.notna(row["age"]) and row["age"] > 45:
            return "Old (no deadline)"
        return "Date unknown"
    if d < 0:
        return "Expired"
    return "Closing soon" if d <= 7 else "Open"


df["status"] = df.apply(status, axis=1)

# ---------------- Clean ----------------
df = df[~df["id"].isin(hidden_ids)]
df = df[~df.apply(is_junk, axis=1)]
df = df[df["title"].apply(looks_like_job)]
df = df.drop_duplicates(subset=["url"])
df["_key"] = (df["title"].str.lower().str.replace(r"\W+", " ", regex=True).str.strip()
              + "|" + df["organization"].astype(str))
df = df.drop_duplicates(subset=["_key"])

counts = df["status"].value_counts()
n_soon = int(counts.get("Closing soon", 0))
n_open = int(counts.get("Open", 0)) + n_soon
n_unknown = int(counts.get("Date unknown", 0))
n_old = int(counts.get("Expired", 0)) + int(counts.get("Old (no deadline)", 0))

# ---------------- Summary cards ----------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("Open now", n_open)
m2.metric("Closing within 7 days", n_soon)
m3.metric("Unknown closing date", n_unknown)
m4.metric("Expired / old", n_old)

# ---------------- Sidebar ----------------
st.sidebar.markdown("### 🔎 Filters")
STATUSES = ["Closing soon", "Open", "Date unknown", "Old (no deadline)", "Expired"]
chosen = st.sidebar.multiselect("Show", STATUSES, default=["Closing soon", "Open"])
search = st.sidebar.text_input("Search title", placeholder="engineer, IT, data ...")
orgs = st.sidebar.multiselect("Organization", sorted(df["organization"].dropna().unique()))
max_days = st.sidebar.slider("Closes within (days)", 1, 365, 365)
sort_by = st.sidebar.selectbox(
    "Sort by", ["Closing soonest", "Newest posted", "Organization A-Z"])

df = df[df["status"].isin(chosen)]
df = df[df["days_left"].isna() | (df["days_left"] <= max_days)]
if orgs:
    df = df[df["organization"].isin(orgs)]
if search:
    words = [w for w in re.split(r"[,\s]+", search) if w]
    df = df[df["title"].str.contains("|".join(re.escape(w) for w in words),
                                     case=False, na=False)]

order = {"Closing soon": 0, "Open": 1, "Date unknown": 2,
         "Old (no deadline)": 3, "Expired": 4}
if sort_by == "Closing soonest":
    df = df.assign(_o=df["status"].map(order)).sort_values(["_o", "days_left", "title"])
elif sort_by == "Newest posted":
    df = df.sort_values("posted", ascending=False, na_position="last")
else:
    df = df.sort_values(["organization", "title"])
df["days_left"] = df["days_left"].astype("Int64")

# ---------------- Toolbar ----------------
st.write("")
t1, t2, t3 = st.columns([3, 3, 2])
view = t1.radio("View", ["Cards", "Table"], horizontal=True, label_visibility="collapsed")
t2.markdown(f"**{len(df)}** jobs match your filters")
export = df[["title", "organization", "posted", "closes", "days_left", "status", "url"]]
t3.download_button("⬇ Download CSV", export.to_csv(index=False).encode("utf-8"),
                   file_name="jobs.csv", mime="text/csv")

if df.empty:
    st.info("No jobs match these filters. Try adding 'Date unknown' under Show.")
    st.stop()

BADGE = {"Closing soon": "b-soon", "Open": "b-open", "Date unknown": "b-unknown",
         "Old (no deadline)": "b-old", "Expired": "b-old"}

# ---------------- Cards view ----------------
if view == "Cards":
    p1, p2 = st.columns([1, 1])
    page_size = p1.selectbox("Jobs per page", [20, 50, 100], index=0)
    pages = max(1, -(-len(df) // page_size))
    page = p2.number_input("Page", 1, pages, 1) if pages > 1 else 1
    chunk = df.iloc[(page - 1) * page_size: page * page_size]

    for _, r in chunk.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([5, 3, 1.6, 2.2], vertical_alignment="center")
            c1.markdown(
                f'<div class="job-title">{html.escape(str(r["title"]))}</div>'
                f'<div class="job-org">🏛 {html.escape(str(r["organization"]))}</div>',
                unsafe_allow_html=True)

            if pd.notna(r["closes"]):
                dl = int(r["days_left"])
                left = ("closes today" if dl == 0 else
                        "1 day left" if dl == 1 else
                        f"{dl} days left" if dl > 0 else f"closed {-dl} days ago")
                when = f'⏰ <b>{r["closes"]:%d %b %Y}</b><br><small>{left}</small>'
            else:
                when = "⏰ Closing date unknown"
            if pd.notna(r["posted"]):
                when += f'<br><small>Posted {r["posted"]:%d %b %Y}</small>'
            c2.markdown(f'<div class="job-when">{when}</div>', unsafe_allow_html=True)

            c3.markdown(
                f'<span class="badge {BADGE[r["status"]]}">{r["status"]}</span>',
                unsafe_allow_html=True)

            b1, b2 = c4.columns(2)
            b1.link_button("Open ad", str(r["url"]))
            if b2.button("✕", key=f"hide_{r['id']}", help="Not a job: hide this"):
                conn.execute("INSERT OR IGNORE INTO hidden_jobs (job_id) VALUES (?)",
                             (int(r["id"]),))
                conn.commit()
                st.rerun()

# ---------------- Table view ----------------
else:
    tbl = df.copy()
    tbl["hide"] = False
    edited = st.data_editor(
        tbl[["hide", "id", "title", "organization", "posted", "closes",
             "days_left", "status", "url"]],
        width="stretch",
        hide_index=True,
        key="jobs_table",
        column_order=["hide", "title", "organization", "posted", "closes",
                      "days_left", "status", "url"],
        disabled=["id", "title", "organization", "posted", "closes",
                  "days_left", "status", "url"],
        column_config={
            "hide": st.column_config.CheckboxColumn("Not a job?"),
            "title": st.column_config.TextColumn("Job", width="large"),
            "organization": "Organization",
            "posted": st.column_config.DateColumn("Posted", format="DD MMM YYYY"),
            "closes": st.column_config.DateColumn("Closes", format="DD MMM YYYY"),
            "days_left": st.column_config.NumberColumn("Days left"),
            "status": "Status",
            "url": st.column_config.LinkColumn("Link", display_text="Open"),
        },
    )
    if st.button("Hide ticked rows (not a job)"):
        ids = [int(i) for i in edited.loc[edited["hide"], "id"]]
        if ids:
            conn.executemany("INSERT OR IGNORE INTO hidden_jobs (job_id) VALUES (?)",
                             [(i,) for i in ids])
            conn.commit()
            st.rerun()

# ---------------- Hidden rows ----------------
st.write("")
with st.expander(f"Hidden by you ({len(hidden_ids)})"):
    if st.button("Restore all hidden rows"):
        conn.execute("DELETE FROM hidden_jobs")
        conn.commit()
        st.rerun()