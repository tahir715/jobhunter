import pandas as pd
from server import load_jobs

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 70)

df, hidden = load_jobs()


def kind(u):
    u = str(u).lower().split("?")[0]
    if u.endswith(".pdf"):
        return "PDF"
    if u.endswith((".jpg", ".jpeg", ".png", ".gif")):
        return "Image"
    if u.endswith((".doc", ".docx")):
        return "Word"
    return "Web page"


df["type"] = df["url"].apply(kind)

print("\n=== ALL JOBS BY STATUS ===")
print(df["status"].value_counts().to_string())

unk = df[df["status"] == "Date unknown"].copy()
print(f"\n=== {len(unk)} JOBS WITH NO CLOSING DATE: BY FILE TYPE ===")
print(unk["type"].value_counts().to_string())

print("\n=== BY ORGANIZATION (top 15) ===")
print(unk["organization"].value_counts().head(15).to_string())

print("\n=== 15 RANDOM EXAMPLES ===")
sample = unk.sample(min(15, len(unk)), random_state=1)
print(sample[["organization", "type", "title"]].to_string(index=False))

unk[["organization", "type", "title", "url"]].to_csv(
    "data/unknown_dates.csv", index=False, encoding="utf-8-sig")
print("\nSaved the full list to data/unknown_dates.csv")