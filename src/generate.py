"""MODEL-CALLING STEP. 40 claims x 2 arms (bare question, question + evidence summary)
x 2 system prompts (neutral, operator) = 160 calls per evaluated role.
Usage: python3 generate.py <role> [--dry-run]     role in evaluated_1, evaluated_2
Order: randomized per role (seed 20261116). Resumable (deterministic call_id)."""
import random, sys
from common import CALLS, CLAIMS, PROMPTS, SYSTEM_PROMPTS, load_roles, read_jsonl

def plan(role):
    claims = read_jsonl(CLAIMS); assert len(claims) == 40
    tpl = (PROMPTS / "user_evidence_template.txt").read_text().strip()
    items = []
    for c in claims:
        for arm in ("bare", "evidence"):
            user = c["question"] if arm == "bare" else tpl.format(evidence=c["evidence_summary"], question=c["question"])
            for pname in ("neutral", "operator"):
                items.append({"call_id": f"EA/gen/{c['id']}/{arm}/{pname}/{role}", "claim_id": c["id"],
                              "arm": arm, "prompt_name": pname, "role": role, "user": user})
    random.Random(f"20261116-{role}").shuffle(items)
    return items

def main():
    role = sys.argv[1]; items = plan(role)
    systems = {k: p.read_text().strip() for k, p in SYSTEM_PROMPTS.items()}
    if "--dry-run" in sys.argv:
        print(len(items), "calls; first:", items[0]["call_id"]); print(items[0]["user"]); return 0
    r = load_roles()[role]
    from llm_cli import call
    CALLS.mkdir(parents=True, exist_ok=True)
    for n, it in enumerate(items, 1):
        rec = call(cli=r["cli"], model=r["model"], prompt=it["user"], system=systems[it["prompt_name"]],
                   effort=r.get("effort", "medium"), call_id=it["call_id"], log_path=CALLS / f"generation_{role}.jsonl",
                   meta={"topic": "EA", "step": "generation", "role": role, "claim_id": it["claim_id"],
                         "arm": it["arm"], "prompt_name": it["prompt_name"]})
        print(f"[{n}/{len(items)}] {it['call_id']} -> {rec['status']}", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
