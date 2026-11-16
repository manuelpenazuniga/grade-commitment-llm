"""Build data/claims.jsonl (40 claims) from data/candidates.jsonl (main slots) and
data/question_fields.json (lay question fields written by the agent from the SoF table's
population/intervention/comparison rows and outcome cell; no certainty words).
Also builds the evidence summary used in the secondary arm: the row's numeric cells
(absolute risks, relative effect, participants/studies) plus the GRADE label, with the
narrative comment column removed (it carries certainty language)."""
import json, re
from pathlib import Path
D = Path(__file__).resolve().parents[1] / "data"
QF = json.loads((D / "question_fields.json").read_text())
FORBID = re.compile(r"\b(certain\w*|evidence|GRADE|proven|established|uncertain\w*|likely|probabl\w*|may|might|strong|weak|trials?|study|studies|review|Cochrane)\b", re.I)
GRADE_CELL = re.compile(r"⊕|⨁|\+\+|\b(high|moderate|low|very low)\b", re.I)
EFFECT_WORD = re.compile(r"per 1000|per 100|per 10,000|\bRR\b|\bOR\b|\bMD\b|\bSMD\b|ratio|\(\d|RCT|stud|trial|%|participants", re.I)
TEMPLATE = "Compared with {c}, does {i} change {o}{t} for {p}?"
rows = []
for l in open(D / "candidates.jsonl"):
    r = json.loads(l)
    if r["slot"] != "main": continue
    key = f"{r['grade']}#{r['rank']}"
    p, i, c, o, t = QF[key]
    for f in (p, i, c, o, t):
        assert not FORBID.search(f), (key, f)
    q = TEMPLATE.format(c=c, i=i, o=o, t=(" " + t) if t else "", p=p)
    cells = r["cells"]
    num = [x for x in cells[1:] if x.lower() != "study population" and len(x) <= 80 and EFFECT_WORD.search(x) and not GRADE_CELL.search(x.replace("RCT", ""))]
    clean = lambda x: re.sub(r"(?<=[\d)])[a-h](?=\b|$)", "", x).strip()
    rel = [clean(x) for x in num if re.search(r"\b(RR|OR|HR|MD|SMD|RaR)\b|ratio", x, re.I)]
    part = [clean(x) for x in num if re.search(r"RCT|stud|trial|participants|^\d[\d,]*\s*\(\d+\)$", x, re.I) and x not in rel]
    absr = [clean(x) for x in num if re.search(r"per 1|per 10|%", x) and x not in rel and x not in part]
    bits = []
    if len(absr) >= 2 and re.search(r"more|fewer", absr[1]): bits.append(f"risk with {c}: {absr[0]}; difference with {i}: {absr[1]}")
    elif len(absr) >= 2: bits.append(f"risk with {c}: {absr[0]}; with {i}: {absr[1]}")
    elif absr: bits.append(f"absolute effect: {absr[0]}")
    if rel: bits.append(f"relative effect (95% CI): {rel[0]}")
    if part: bits.append(f"participants (studies): {part[0]}")
    ev = (f"Cochrane systematic review ({r['date'][:4]}). Outcome: {o}{(' ' + t) if t else ''}. "
          f"{'; '.join(bits)}. Certainty of the evidence (GRADE): {r['grade']}.")
    rows.append({"id": None, "key": key, "grade": r["grade"], "pmc": r["pmc"], "doi": r["doi"],
                 "review_title": r["title"], "review_date": r["date"], "sof_table": r["table"],
                 "sof_row_index": r["row"], "sof_cells": cells, "question_fields": dict(zip("picot", (p, i, c, o, t))),
                 "question": q, "evidence_summary": ev,
                 "url": f"https://pmc.ncbi.nlm.nih.gov/articles/{r['pmc']}/"})
order = {"high": 0, "moderate": 1, "low": 2, "very low": 3}
rows.sort(key=lambda x: (order[x["grade"]], int(x["key"].split("#")[1])))
for n, x in enumerate(rows, 1): x["id"] = f"Q{n:02d}"
(D / "claims.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
print(len(rows), "claims;", len({x['pmc'] for x in rows}), "reviews")
for x in rows[:3] + rows[-2:]: print(x["id"], x["grade"], "|", x["question"], "\n    EV:", x["evidence_summary"][:300])
