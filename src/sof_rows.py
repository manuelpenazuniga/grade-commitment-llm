"""Parse every Summary of Findings table in data/raw/*.xml into candidate rows with a
mechanically detected GRADE level. Output: data/sof_rows.jsonl (reading aid for curation)."""
import json, re
import xml.etree.ElementTree as ET
from pathlib import Path
D = Path(__file__).resolve().parents[1] / "data"
def tx(el): return " ".join("".join(el.itertext()).split())
PAT = [("very low", re.compile(r"very\s*low|⊕⊝⊝⊝|⊕◯◯◯|⊕OOO|\+ooo", re.I)),
       ("low", re.compile(r"\blow\b|⊕⊕⊝⊝|⊕⊕◯◯|⊕⊕OO|\+\+oo", re.I)),
       ("moderate", re.compile(r"moderate|⊕⊕⊕⊝|⊕⊕⊕◯|⊕⊕⊕O|\+\+\+o", re.I)),
       ("high", re.compile(r"\bhigh\b|⊕⊕⊕⊕|\+\+\+\+", re.I))]
def grade_of(cell):
    c = cell.strip()
    if len(c) > 60: return None
    for g, p in PAT:
        if p.search(c): return g
    return None
out = []
for f in sorted((D / "raw").glob("PMC*.xml")):
    root = ET.parse(f).getroot()
    t = root.find(".//article-meta/title-group/article-title")
    title = tx(t) if t is not None else ""
    doi = root.findtext(".//article-meta/article-id[@pub-id-type='doi']")
    if not (doi or "").startswith("10.1002/14651858"): continue
    d = root.find(".//article-meta/pub-date[@pub-type='epub']")
    d = d if d is not None else root.find(".//article-meta/pub-date")
    date = "-".join((d.findtext(k) or "") for k in ("year", "month", "day")) if d is not None else ""
    for ti, tw in enumerate(root.iter("table-wrap")):
        cap, lab = tw.find("caption"), tw.find("label")
        head = ((tx(lab) if lab is not None else "") + " " + (tx(cap) if cap is not None else "")).strip()
        if "summary of findings" not in head.lower(): continue
        for ri, tr in enumerate(tw.iter("tr")):
            cells = [tx(c) for c in tr if c.tag in ("td", "th")]
            if len(cells) < 3: continue
            gs = [grade_of(c) for c in cells[1:]]
            gs = [g for g in gs if g]
            if len(gs) != 1: continue
            out.append({"pmc": f.stem, "doi": doi, "title": title, "date": date, "table": head[:200],
                        "row": ri, "cells": cells, "grade": gs[0]})
(D / "sof_rows.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
from collections import Counter
print(len(out), "rows;", Counter(r["grade"] for r in out))
print("reviews with rows:", len({r["pmc"] for r in out}))
for g in ("high","moderate","low","very low"):
    print(g, "reviews:", len({r["pmc"] for r in out if r["grade"]==g}))
