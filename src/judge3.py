"""EXPLORATORY (not pre-registered; added 2026-11-16 07:55 after the primary results). Third judge:
Claude Opus 5.5 (claude CLI, effort high) on the same 96-response subsample as judge2,
same rubric and inputs as the primary judge.
GRADE x model x arm x prompt cell (32 cells, 96 calls), claims drawn with seed 20261117.
Family overlap: Opus (Anthropic) also judges Sonnet 5.5 outputs; reported by model."""
import json, random, sys
from common import CALLS, CLAIMS, OUT, PROMPTS, ok_calls, parse_judge_json, quote_check, read_jsonl
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "lib"))
from llm_cli import call
from judge import render
claims = {c["id"]: c for c in read_jsonl(CLAIMS)}
gen = {}
for r in ("evaluated_1", "evaluated_2"): gen.update(ok_calls(CALLS / f"generation_{r}.jsonl"))
rng = random.Random(20261117); picks = []
for g in ("high", "moderate", "low", "very low"):
    ids = sorted(c for c in claims if claims[c]["grade"] == g)
    for role in ("evaluated_1", "evaluated_2"):
        for arm in ("bare", "evidence"):
            for p in ("neutral", "operator"):
                for cid in rng.sample(ids, 3): picks.append(f"EA/gen/{cid}/{arm}/{p}/{role}")
rng.shuffle(picks)
system = (PROMPTS / "judge_system.txt").read_text().strip()
outp = OUT / "judge3_generation.jsonl"
done = {json.loads(l)["item"] for l in open(outp)} if outp.exists() else set()
import os
K, N = map(int, os.environ.get('SHARD', '0/1').split('/'))
for n, cid in enumerate(picks, 1):
    if cid in done or n % N != K: continue
    rec0 = gen[cid]; cl = claims[rec0["meta"]["claim_id"]]
    rec = call(cli="claude", model="claude-opus-5-5", prompt=render(cl["question_fields"], rec0["text"]), system=system,
               effort="high", call_id=cid.replace("EA/gen/", "EA/judge3/gen/"), log_path=CALLS / "judge3_generation.jsonl",
               meta={"topic": "EA", "step": "judge3", "item": cid})
    labels, err = (None, f"call status {rec['status']}")
    if rec["status"] == "ok": labels, err = parse_judge_json(rec["text"])
    with open(outp, "a") as fh:
        fh.write(json.dumps({"item": cid, "claim_id": cl["id"], "parse_error": err, "labels": labels,
                             "quote_found": quote_check(labels, rec0["text"]) if labels else None}) + "\n")
    print(f"[{n}/96] {cid} -> {rec['status']} {err or ''}", flush=True)
