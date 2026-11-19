import re
from enrich import get_text, DATE_RE
from server import load_jobs

df, _ = load_jobs()
unk = df[df["status"] == "Date unknown"]
KEY = re.compile(r"(last date|deadline|closing|apply (?:by|before|till|until)|"
                 r"due date|submit|on or before|not later than|valid)", re.I)


def show(org, n):
    for _, r in unk[unk["organization"] == org].head(n).iterrows():
        print("=" * 90)
        print(org, "|", r["title"])
        print(r["url"])
        text = get_text(r["url"])
        if text is None:
            print("  -> COULD NOT LOAD")
            continue
        text = re.sub(r"\s+", " ", text)
        print(f"  text length: {len(text)}")
        for m in list(KEY.finditer(text))[:4]:
            print("  KEY:", text[max(0, m.start() - 80): m.end() + 120])
        print("  DATES FOUND:", [m.group() for m in DATE_RE.finditer(text)][:6])


for org, n in [("Air University", 3), ("Power Division", 3),
               ("Ministry of IT & Telecom", 2), ("National Skills University", 2)]:
    show(org, n)