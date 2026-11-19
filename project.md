# Job Hunter
Python tool that tracks federal job openings, shows open/closed
status and deadlines, scores my CV match, and alerts me by Gmail/Telegram.
I apply manually. No auto-apply.

Stack: Python, Streamlit, SQLite, Playwright, BeautifulSoup.

Rules:
- One scraper per website in scrapers/, each returns a list of dicts
- Job fields: title, organization, url, posted_date, deadline, status
- Keep code simple, commented, beginner-friendly
- Never hardcode secrets

Build order:
1. Database + scrapers
2. Streamlit dashboard
3. CV matcher
4. Alerts + Gmail watcher