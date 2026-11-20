import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(*args):
    print(">", " ".join(args))
    return subprocess.run(list(args)).returncode


py = sys.executable
print("Step 1/3: scanning websites...")
run(py, "watcher.py")
print("\nStep 2/3: reading closing dates...")
run(py, "enrich.py")
print("\nStep 3/3: uploading to the website...")
Path("data/last_scan.txt").write_text(
    datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"), encoding="utf-8")
run("git", "add", "data/jobs.db", "data/last_scan.txt")
if run("git", "diff", "--cached", "--quiet") != 0:
    run("git", "commit", "-m", "Update jobs database")
    run("git", "push")
    print("\nUploaded. The site refreshes in a minute or two.")
else:
    print("\nNo new data to upload.")