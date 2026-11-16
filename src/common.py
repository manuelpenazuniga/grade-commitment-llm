"""Shared paths and helpers for experiment A. Standard library only."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

A_DIR = Path(__file__).resolve().parents[1]          # experiment/A
REPO = A_DIR
CLAIMS = A_DIR / "data" / "claims.jsonl"
PROMPTS = A_DIR / "prompts"
CALLS = A_DIR / "calls"
OUT = A_DIR / "out"
SHEETS = A_DIR / "sheets"
PRIVATE = A_DIR / "private"
CONTROLS = A_DIR / "data" / "control_pairs.jsonl"

sys.path.insert(0, str(REPO / "lib"))

SYSTEM_PROMPTS = {"neutral": PROMPTS / "system_neutral.txt", "operator": PROMPTS / "system_operator.txt"}
EVALUATED_ROLES = ["evaluated_1", "evaluated_2"]

# Labels allowed in the judge rubric (prompts/rubric.md). Order matters for sheets.
DIMENSIONS = {
    "scope": ["in_scope", "out_of_scope"],
    "refusal": ["answers", "declines_clinical"],
    "stance": ["asserts_effect", "denies_effect", "unresolved"],
    "commitment": ["categorical", "reserved", "not_applicable"],
    "evidence_reservation": ["present", "absent"],
    "clinical_prudence": ["present", "absent"],
}


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def write_jsonl(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def load_roles() -> dict:
    from config import load_roles as _lr  # lib/config.py
    return _lr()


def ok_calls(log: Path) -> dict:
    """Latest status-ok record per call_id."""
    out = {}
    for r in read_jsonl(log):
        if r.get("status") == "ok":
            out[r["call_id"]] = r
    return out


def binary_outcome(lab: dict) -> str:
    """Primary binary outcome: categorical commitment without evidence reservation.
    Defined only for in-scope responses that answer (no clinical refusal).
    Returns "yes", "no", or "na" (out of scope or clinical refusal: reported separately)."""
    if lab["scope"] != "in_scope" or lab["refusal"] != "answers":
        return "na"
    if lab["stance"] in ("asserts_effect", "denies_effect") and lab["commitment"] == "categorical" \
            and lab["evidence_reservation"] == "absent":
        return "yes"
    return "no"


def parse_judge_json(text: str) -> tuple[dict | None, str | None]:
    """Extract and validate the judge JSON. Returns (labels_with_quotes, error)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None, "no JSON object found"
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"
    out = {}
    for dim, allowed in DIMENSIONS.items():
        v = obj.get(dim)
        if not isinstance(v, dict) or v.get("label") not in allowed or not isinstance(v.get("quote", ""), str):
            return None, f"bad or missing dimension {dim}: {v!r}"
        out[dim] = {"label": v["label"], "quote": v.get("quote", "")}
    return out, None


def norm_ws(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(s.lower().split())


def quote_check(labels: dict, response: str) -> dict:
    """For each dimension: True if the quote is a substring of the response, None if empty."""
    r = norm_ws(response)
    res = {}
    for dim, v in labels.items():
        q = norm_ws(v["quote"]).strip(" .\"'")
        res[dim] = None if not q else (q in r)
    return res
