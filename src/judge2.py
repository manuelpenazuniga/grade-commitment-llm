"""EXPLORATORY (not pre-registered; added 2026-11-16 01:05 before the primary judge finished).
Second judge on a stratified subsample for inter-judge robustness: GPT-6 Astra (codex CLI,
effort medium), same rubric and inputs as the primary judge. 3 responses per
GRADE x model x arm x prompt cell (32 cells, 96 calls), claims drawn with seed 20261117.
Family overlap: Astra (OpenAI) also judges GPT-6.1 Sol outputs; reported by model."""
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
outp = OUT / "judge2_generation.jsonl"
done = {json.loads(l)["item"] for l in open(outp)} if outp.exists() else set()
for n, cid in enumerate(picks, 1):
    if cid in done: continue
    rec0 = gen[cid]; cl = claims[rec0["meta"]["claim_id"]]
    rec = call(cli="codex", model="gpt-6-astra", prompt=render(cl["question_fields"], rec0["text"]), system=system,
               effort="medium", call_id=cid.replace("EA/gen/", "EA/judge2/gen/"), log_path=CALLS / "judge2_generation.jsonl",
               meta={"topic": "EA", "step": "judge2", "item": cid})
    labels, err = (None, f"call status {rec['status']}")
    if rec["status"] == "ok": labels, err = parse_judge_json(rec["text"])
    with open(outp, "a") as fh:
        fh.write(json.dumps({"item": cid, "claim_id": cl["id"], "parse_error": err, "labels": labels,
                             "quote_found": quote_check(labels, rec0["text"]) if labels else None}) + "\n")
    print(f"[{n}/96] {cid} -> {rec['status']} {err or ''}", flush=True)
