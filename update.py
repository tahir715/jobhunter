import subprocess
import sys
from datetime import datetime

print(f"=== Update started {datetime.now():%d %b %Y %H:%M} ===\n")

print("Step 1/2: scanning websites for new jobs...")
subprocess.run([sys.executable, "watcher.py"])

print("\nStep 2/2: reading closing dates from new jobs...")
subprocess.run([sys.executable, "enrich.py"])

print("\n=== All done. Refresh the dashboard in your browser. ===")