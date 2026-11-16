"""MODEL-CALLING STEP. Judge (role 'judge') labels responses with prompts/judge_system.txt.
The judge sees ONLY the claim fields (p,i,c,o,t) and the response text: never GRADE, arm,
evidence summary, model or system prompt.
  python3 judge.py controls            # 18 pairs x 2 versions = 36 calls (seed 20261116)
  python3 judge.py generation [--follow]  # all ok generation calls; --follow keeps polling
                                          # until all 320 are judged. Order: shuffled batches."""
import json, random, sys, time
from common import CALLS, CLAIMS, CONTROLS, OUT, PROMPTS, ok_calls, parse_judge_json, quote_check, read_jsonl, load_roles

def render(f, response):
    f = {**f, "t": f.get("t") or "(not specified)"}
    return (PROMPTS / "judge_user_template.txt").read_text().format(response=response.strip(), **f)

def judge_items(items, mode, role, system, log, outp, rng):
    from llm_cli import call
    done = {json.loads(l)["judge_call_id"] for l in open(outp)} if outp.exists() else set()
    items = [x for x in items if x["call_id"] not in done]
    rng.shuffle(items)
    for it in items:
        rec = call(cli=role["cli"], model=role["model"], prompt=render(it["fields"], it["response"]), system=system,
                   effort=role.get("effort", "medium"), call_id=it["call_id"], log_path=log,
                   meta={"topic": "EA", "step": f"judge_{mode}", "item": it["item"]})
        labels, err = (None, f"call status {rec['status']}")
        if rec["status"] == "ok":
            labels, err = parse_judge_json(rec["text"])
        row = {"item": it["item"], "claim_id": it["claim_id"], "judge_call_id": it["call_id"], "parse_error": err,
               "labels": labels, "quote_found": quote_check(labels, it["response"]) if labels else None}
        with open(outp, "a") as fh: fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{it['item']} -> {rec['status']} {err or ''}", flush=True)
    return len(items)

def main():
    mode = sys.argv[1]
    claims = {c["id"]: c for c in read_jsonl(CLAIMS)}
    fields = lambda cid: claims[cid]["question_fields"]
    system = (PROMPTS / "judge_system.txt").read_text().strip()
    role = load_roles()["judge"]; OUT.mkdir(exist_ok=True); CALLS.mkdir(exist_ok=True)
    rng = random.Random(20261116)
    log, outp = CALLS / f"judge_{mode}.jsonl", OUT / f"judge_{mode}.jsonl"
    if mode == "controls":
        items = [{"call_id": f"EA/judge/ctrl/{p['pair_id']}/{v}", "item": f"{p['pair_id']}/{v}", "claim_id": p["claim_id"],
                  "response": p[f"version_{v}"], "fields": fields(p["claim_id"])} for p in read_jsonl(CONTROLS) for v in "ab"]
        judge_items(items, mode, role, system, log, outp, rng); return 0
    while True:
        gen = {}
        for r in ("evaluated_1", "evaluated_2"): gen.update(ok_calls(CALLS / f"generation_{r}.jsonl"))
        items = [{"call_id": cid.replace("EA/gen/", "EA/judge/gen/"), "item": cid, "claim_id": rec["meta"]["claim_id"],
                  "response": rec["text"], "fields": fields(rec["meta"]["claim_id"])} for cid, rec in sorted(gen.items())]
        n = judge_items(items, mode, role, system, log, outp, rng)
        ndone = sum(1 for _ in open(outp)) if outp.exists() else 0
        if "--follow" not in sys.argv or ndone >= 320: print("judged", ndone); return 0
        if n == 0: time.sleep(45)

if __name__ == "__main__":
    sys.exit(main())
