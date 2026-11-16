"""Fixed, mechanical selection of candidate SoF rows (written before any model call of the
experiment; uses only SoF table text). Rule:
  R1 table caption describes a comparison ('compared to', 'compared with', 'versus', ' vs ')
     and is not a qualitative/CERQual table;
  R2 the row has exactly one cell with a GRADE level and a cell with an effect estimate
     (RR, OR, HR, RaR, MD, SMD, risk/rate ratio) with a 95% CI in parentheses;
  R3 the outcome cell (first cell) is not an adverse-event, safety, cost, attrition or
     'not reported' outcome;
  R4 reviews are visited in a random order (seed 20261116); for each GRADE level the
     first eligible row (table order) of each review is taken, at most one row per review
     per level and at most two rows per review overall, levels filled in the order
     high, very low, moderate, low (scarcest first);
  R4b one version per Cochrane review (CD number in the DOI; the most recent version is kept);
      rows whose first cell is not an outcome label (starts with a digit) are dropped;
  R5 10 rows per level plus 6 reserves. A row is replaced by the next reserve only if no
     lay patient question can be written from it (reason logged in data/curation_log.md).
"""
import json, random, re
from pathlib import Path
D = Path(__file__).resolve().parents[1] / "data"
rows = [json.loads(l) for l in open(D / "sof_rows.jsonl")]
CMP = re.compile(r"compared (to|with)|versus| vs\.? ", re.I)
QUAL = re.compile(r"qualitative|cerqual|confidence in|review finding", re.I)
EFF = re.compile(r"\b(RR|OR|HR|RaR|MD|SMD|risk ratio|rate ratio|odds ratio|hazard ratio|mean difference)\b[^()]{0,40}\(\s*-?[\d.]+\s*(to|,)\s*-?[\d.]+", re.I)
BAD = re.compile(r"\bSAE\b|adverse|side.?effect|harm|safety|withdraw|dropout|drop-out|attrition|cost|toxicit|not (measured|reported)|no (studies|data)|serious", re.I)
def eligible(r):
    if not CMP.search(r["table"]) or QUAL.search(r["table"]): return False
    if not any(EFF.search(c) for c in r["cells"][1:]): return False
    if BAD.search(r["cells"][0]): return False
    return True
def cd(r):
    m = re.search(r"(CD|MR)\d+", r["doi"]); return m.group(0) if m else r["doi"]
latest = {}
for r in rows:
    k = cd(r); key = tuple(int(x) for x in r["date"].split("-") if x)
    if k not in latest or key > latest[k][0]: latest[k] = (key, r["pmc"])
el = [r for r in rows if eligible(r) and latest[cd(r)][1] == r["pmc"] and not r["cells"][0][:1].isdigit()]
reviews = sorted({r["pmc"] for r in el}); random.Random(20261116).shuffle(reviews)
used_total, picked = {}, {g: [] for g in ("high", "very low", "moderate", "low")}
for g in picked:
    for pmc in reviews:
        if len(picked[g]) >= 16: break
        if used_total.get(pmc, 0) >= 2: continue
        cand = [r for r in el if r["pmc"] == pmc and r["grade"] == g]
        if cand:
            picked[g].append(cand[0]); used_total[pmc] = used_total.get(pmc, 0) + 1
out = []
for g, lst in picked.items():
    for i, r in enumerate(lst):
        out.append({**r, "slot": "main" if i < 10 else "reserve", "rank": i})
(D / "candidates.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
print("eligible rows", len(el), "reviews", len(reviews))
for g, lst in picked.items(): print(g, len(lst))
