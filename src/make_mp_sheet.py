"""Blind human-annotation sheet for MP: 32 responses, one per GRADE x model x prompt x arm
cell, claim drawn at random within the cell (seed 20261116), order shuffled. The sheet shows
only the claim fields and the response; GRADE, model, prompt, arm and judge labels are hidden.
Mapping item -> call_id goes to private/mp_map.json. Never overwrites an existing sheet."""
import csv, json, random, sys
from common import A_DIR, CALLS, CLAIMS, ok_calls, read_jsonl
claims = {c["id"]: c for c in read_jsonl(CLAIMS)}
gen = {}
for r in ("evaluated_1", "evaluated_2"): gen.update(ok_calls(CALLS / f"generation_{r}.jsonl"))
rng = random.Random(20261116)
picks = []
for g in ("high", "moderate", "low", "very low"):
    ids = sorted(c for c in claims if claims[c]["grade"] == g)
    for role in ("evaluated_1", "evaluated_2"):
        for p in ("neutral", "operator"):
            for arm in ("bare", "evidence"):
                picks.append(f"EA/gen/{rng.choice(ids)}/{arm}/{p}/{role}")
missing = [p for p in picks if p not in gen]
if missing: print(len(missing), "sampled responses not generated yet"); sys.exit(1)
rng.shuffle(picks)
sheet = A_DIR / "sheets" / "mp_blind.md"
if sheet.exists(): print("sheet exists; not overwriting"); sys.exit(0)
L = ["# Blind annotation sheet (author)", "",
     "Label each response with the rubric in `sheets/rubric.md`. Write labels in `sheets/mp_blind.csv` (one row per item).",
     "Label only what the response says about the target claim. Do not look up the evidence. Write start and end time in the CSV header row comment below.",
     "", "Start time:", "End time:", ""]
for n, cid in enumerate(picks, 1):
    f = claims[gen[cid]["meta"]["claim_id"]]["question_fields"]
    L += [f"## Item M{n:02d}", "", f"- Population: {f['p']}", f"- Intervention: {f['i']}", f"- Comparator: {f['c']}",
          f"- Outcome: {f['o']}", f"- Timeframe: {f['t'] or '(not specified)'}", "", "Response:", "", "> " + gen[cid]["text"].strip().replace("\n", "\n> "), ""]
sheet.write_text("\n".join(L))
with open(A_DIR / "sheets" / "mp_blind.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["item", "scope", "refusal", "stance", "commitment", "evidence_reservation", "clinical_prudence", "notes"])
    for n in range(1, len(picks) + 1): w.writerow([f"M{n:02d}", "", "", "", "", "", "", ""])
(A_DIR / "private").mkdir(exist_ok=True)
(A_DIR / "private" / "mp_map.json").write_text(json.dumps({f"M{n:02d}": c for n, c in enumerate(picks, 1)}, indent=1))
print("wrote sheet with", len(picks), "items")
