"""
Hash the normalized name+description used for TF-IDF, keep one document
per unique hash, and write a deduplicated JSONL for re-running TF-IDF.
"""
import hashlib
import json
import re
from pathlib import Path
from collections import Counter

FRONTMATTER_BOUNDARY_RE = re.compile(r"^---\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^(name|description):\s*(.*)$", re.MULTILINE)

def strip_quotes(v):
    v = v.strip()
    if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
        return v[1:-1].strip()
    return v

def extract_name_description(text):
    boundaries = list(FRONTMATTER_BOUNDARY_RE.finditer(text))
    if len(boundaries) < 2:
        return "", ""
    start, end = boundaries[0].end(), boundaries[1].start()
    fm = text[start:end]
    values = {"name": "", "description": ""}
    for m in FIELD_RE.finditer(fm):
        values[m.group(1)] = strip_quotes(m.group(2))
    return values["name"], values["description"]

def normalize(s):
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--out-dedup-jsonl", required=True)
args = parser.parse_args()

input_path = Path(args.input)
seen_hashes = {}
total = 0
empty_joined = 0

with input_path.open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        doc = json.loads(line)
        total += 1
        text = str(doc.get("text", "") or "")
        name, desc = extract_name_description(text)
        joined = f"{name} {desc}".strip()
        if not joined:
            empty_joined += 1
            continue
        norm = normalize(joined)
        h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        if h not in seen_hashes:
            seen_hashes[h] = {
                "language": doc.get("language", ""),
                "repo": doc.get("repo", ""),
                "relative_path": doc.get("relative_path", ""),
                "name": name,
                "description": desc,
                "name_description": joined,
                "count": 0,
            }
        seen_hashes[h]["count"] += 1

dup_counts = Counter({h: v["count"] for h, v in seen_hashes.items()})
n_unique = len(seen_hashes)
n_with_joined = total - empty_joined

print(f"Total documents: {total}")
print(f"Empty name+description (excluded): {empty_joined}")
print(f"Documents with non-empty name+description: {n_with_joined}")
print(f"Unique (name+description) hashes: {n_unique}")
print(f"Duplication rate: {100*(1 - n_unique/n_with_joined):.1f}% of docs share content with at least one other doc")
print()
print("Top 15 most-repeated (name+description) contents:")
for h, cnt in dup_counts.most_common(15):
    info = seen_hashes[h]
    print(f"  x{cnt:>4}  [{info['language']}]  {info['name_description'][:90]}")

out_path = Path(args.out_dedup_jsonl)
out_path.parent.mkdir(parents=True, exist_ok=True)
with out_path.open("w", encoding="utf-8") as f:
    for h, info in seen_hashes.items():
        f.write(json.dumps({
            "language": info["language"],
            "repo": info["repo"],
            "relative_path": info["relative_path"],
            "text": f"---\nname: {info['name']}\ndescription: {info['description']}\n---\n",
        }) + "\n")

print(f"\nDeduplicated corpus written to {out_path} ({n_unique} unique docs)")