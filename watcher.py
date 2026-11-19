import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from sources import SOURCES
from db import save_jobs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

JOB_WORDS = ["vacanc", "recruit", "advertis", "post of", "posts of",
             "applications are invited", "hiring", "job"]
GATEWAY_WORDS = ["career", "jobs", "vacanc", "recruit", "opportunit"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}


def _get(url):
    """Gov sites often have broken SSL, so retry without verification."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except requests.exceptions.SSLError:
        r = requests.get(url, headers=HEADERS, timeout=20, verify=False)
    r.raise_for_status()
    return r.text


def fetch(url):
    """Try the URL, then the www. version, twice each."""
    candidates = [url]
    if "://www." not in url:
        candidates.append(url.replace("://", "://www.", 1))
    last = None
    for u in candidates:
        for _ in range(2):
            try:
                return _get(u)
            except Exception as e:
                last = e
    raise last


def find_gateways(soup, base):
    """Short links like 'Careers' / 'Jobs' / 'Vacancies' on the homepage."""
    found = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        if 0 < len(text) <= 30 and any(w in text for w in GATEWAY_WORDS):
            link = urljoin(base, a["href"])
            if link != base and link not in found:
                found.append(link)
    return found


def find_jobs(soup, base, org, skip):
    jobs = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        link = urljoin(base, a["href"])
        if not text or link in skip:
            continue
        if any(w in (text + " " + link).lower() for w in JOB_WORDS):
            jobs.append({"title": text[:200], "organization": org, "url": link})
    return jobs


def scan(source):
    home = BeautifulSoup(fetch(source["url"]), "html.parser")
    gateways = find_gateways(home, source["url"])
    pages = [(source["url"], home)]
    for g in gateways[:2]:                      # follow up to 2 careers links
        try:
            pages.append((g, BeautifulSoup(fetch(g), "html.parser")))
        except Exception:
            pass
    jobs, seen = [], set()
    for base, soup in pages:
        for j in find_jobs(soup, base, source["name"], set(gateways)):
            if j["url"] not in seen:
                seen.add(j["url"])
                jobs.append(j)
    return jobs


def run(source):
    if not source["url"]:
        return source, None, "NO URL"
    try:
        return source, scan(source), None
    except Exception as e:
        return source, None, str(e)[:80]


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=8) as ex:   # checks 8 sites at once
        results = list(ex.map(run, SOURCES))

    ok = failed = nourl = 0
    for s, jobs, err in results:
        if err == "NO URL":
            nourl += 1
            print(f"-  {s['name']}: no URL set")
        elif err:
            failed += 1
            print(f"X  {s['name']}: FAILED -> {err}")
        else:
            new = save_jobs(jobs, s["name"])
            ok += 1
            print(f"OK {s['name']}: {len(jobs)} found, {new} new")
    print(f"\nDone. OK: {ok} | Failed: {failed} | No URL: {nourl}")