"""Analysis per PROTOCOL.md, revised after the GPT-6 Astra review (review/astra_prompt_1.answer.md)
before any judge output on generations was inspected. No model calls.
Registered: primary, by-level, secondary contrasts (cluster bootstrap over reviews, 2000, seed 20261116),
controls, human agreement. Exploratory (marked): all-request bounds, paired transitions,
GRADE x CI stratification, leave-one-review-out.
Writes out/results.json, out/results.md, out/rows.json, figures/fig1_by_grade.png.
Run with experiment/A/.venv/bin/python (matplotlib)."""
import csv, json, math, random, statistics, sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import A_DIR, CALLS, CLAIMS, CONTROLS, OUT, read_jsonl, binary_outcome, ok_calls

LEVELS = ["high", "moderate", "low", "very low"]
MODELS = {"evaluated_1": "GPT-6.1 Sol", "evaluated_2": "Claude Sonnet 5.5"}
ARMS, PROMPTS_ = ("bare", "evidence"), ("neutral", "operator")
B, SEED = 2000, 20261116
claims = {c["id"]: c for c in read_jsonl(CLAIMS)}
CI = json.loads((A_DIR / "data" / "ci_fields.json").read_text()); CI.pop("_note", None)


def ci_status(cid):
    if cid not in CI: return "unknown"
    _, lo, hi, nu = CI[cid]
    return "includes null" if lo <= nu <= hi else "excludes null"


gen = {}
for r in MODELS: gen.update(ok_calls(CALLS / f"generation_{r}.jsonl"))
judged = {}
for r in read_jsonl(OUT / "judge_generation.jsonl"):   # keep the last record per item
    judged[r["item"]] = r


def lab(r):
    return {k: v["label"] for k, v in r["labels"].items()} if r and r.get("labels") else None


# ---------------------------------------------------------------- completeness audit (all 320 cells)
rows, audit = [], Counter()
for cid_, c in claims.items():
    for mk in MODELS:
        for arm in ARMS:
            for pr in PROMPTS_:
                call_id = f"EA/gen/{cid_}/{arm}/{pr}/{mk}"
                rec = gen.get(call_id)
                if rec is None:
                    audit["generation_missing"] += 1; status = "gen_missing"; L = None; words = None
                else:
                    j = judged.get(call_id); L = lab(j); words = len(rec["text"].split())
                    if L is None:
                        audit["judgment_missing_or_invalid"] += 1; status = "judge_missing"
                    else:
                        status = binary_outcome(L); audit[f"binary_{status}"] += 1
                rows.append({"call_id": call_id, "claim": cid_, "review": c["pmc"], "grade": c["grade"], "model": mk,
                             "arm": arm, "prompt": pr, "labels": L, "binary": status, "ci": ci_status(cid_), "words": words})
assert len({(r["claim"], r["model"], r["arm"], r["prompt"]) for r in rows}) == 320


def prop(sub):
    v = [r["binary"] for r in sub if r["binary"] in ("yes", "no")]
    return (sum(x == "yes" for x in v) / len(v)) if v else None, len(v), sum(x == "yes" for x in v)


def by_review(rs):
    by = defaultdict(list)
    for r in rs: by[r["review"]].append(r)
    return by


BY = by_review(rows); REVS = sorted(BY)


def boot(stat):
    rng = random.Random(SEED); vals = []
    for _ in range(B):
        samp = [x for rv in (rng.choice(REVS) for _ in REVS) for x in BY[rv]]
        v = stat(samp)
        if v is not None: vals.append(v)
    if not vals: return [None, None]
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 3), round(vals[min(len(vals) - 1, int(0.975 * len(vals)))], 3)]


def P(f): return lambda rs: prop([r for r in rs if f(r)])[0]


def est(f):
    sub = [r for r in rows if f(r)]; p, n, k = prop(sub)
    elig = [r for r in sub if r["binary"] in ("yes", "no")]
    return {"p": None if p is None else round(p, 3), "yes": k, "eligible": n, "cells": len(sub),
            "na": sum(r["binary"] == "na" for r in sub), "missing": sum(r["binary"] in ("gen_missing", "judge_missing") for r in sub),
            "claims": len({r["claim"] for r in elig}), "reviews": len({r["review"] for r in elig}), "ci95": boot(P(f))}


def diff(f1, f2):
    fn = lambda rs: (None if P(f1)(rs) is None or P(f2)(rs) is None else P(f1)(rs) - P(f2)(rs))
    v = fn(rows)
    return {"diff": None if v is None else round(v, 3), "ci95": boot(fn)}


mod = lambda mk: (lambda r: mk == "pooled" or r["model"] == mk)
low = lambda r: r["grade"] in ("low", "very low")
res = {"audit": dict(audit), "n_cells": len(rows), "estimand": "share of in-scope, answering responses with a valid judgment that commit categorically without evidence reservation"}
res["primary_bare_low_verylow"] = {mk: est(lambda r, mk=mk: r["arm"] == "bare" and low(r) and mod(mk)(r)) for mk in list(MODELS) + ["pooled"]}
res["by_level"] = {f"{arm}|{mk}|{g}": est(lambda r, arm=arm, mk=mk, g=g: r["arm"] == arm and r["grade"] == g and mod(mk)(r))
                   for arm in ARMS for mk in list(MODELS) + ["pooled"] for g in LEVELS}
sec = {}
for arm in ARMS:
    for mk in list(MODELS) + ["pooled"]:
        s = lambda r, arm=arm, mk=mk: r["arm"] == arm and mod(mk)(r)
        sec[f"high_minus_verylow|{arm}|{mk}"] = diff(lambda r, s=s: s(r) and r["grade"] == "high", lambda r, s=s: s(r) and r["grade"] == "very low")
        sec[f"operator_minus_neutral|{arm}|{mk}"] = diff(lambda r, s=s: s(r) and r["prompt"] == "operator", lambda r, s=s: s(r) and r["prompt"] == "neutral")
for mk in list(MODELS) + ["pooled"]:
    sec[f"evidence_minus_bare|low+verylow|{mk}"] = diff(lambda r, mk=mk: mod(mk)(r) and low(r) and r["arm"] == "evidence", lambda r, mk=mk: mod(mk)(r) and low(r) and r["arm"] == "bare")
    sec[f"evidence_minus_bare|high|{mk}"] = diff(lambda r, mk=mk: mod(mk)(r) and r["grade"] == "high" and r["arm"] == "evidence", lambda r, mk=mk: mod(mk)(r) and r["grade"] == "high" and r["arm"] == "bare")
res["secondary"] = sec


def rate(sub, f):
    sub = [r for r in sub if r["labels"]]
    return None if not sub else round(sum(1 for r in sub if f(r["labels"])) / len(sub), 3)


comp = {}
for arm in ARMS:
    for mk in MODELS:
        for g in LEVELS:
            sub = [r for r in rows if r["arm"] == arm and r["model"] == mk and r["grade"] == g]
            comp[f"{arm}|{mk}|{g}"] = {"n_labelled": sum(1 for r in sub if r["labels"]),
                "evidence_reservation": rate(sub, lambda L: L["evidence_reservation"] == "present"),
                "categorical": rate(sub, lambda L: L["commitment"] == "categorical"),
                "reserved": rate(sub, lambda L: L["commitment"] == "reserved"),
                "asserts": rate(sub, lambda L: L["stance"] == "asserts_effect"),
                "denies": rate(sub, lambda L: L["stance"] == "denies_effect"),
                "unresolved": rate(sub, lambda L: L["stance"] == "unresolved"),
                "prudence": rate(sub, lambda L: L["clinical_prudence"] == "present"),
                "out_of_scope_or_refusal": rate(sub, lambda L: L["scope"] != "in_scope" or L["refusal"] != "answers")}
res["components"] = comp

# ---------------------------------------------------------------- confound table (claim level) and strata
res["claims_grade_x_ci"] = {g: dict(Counter(ci_status(c) for c, x in claims.items() if x["grade"] == g)) for g in LEVELS}
res["exploratory_grade_x_ci_bare"] = {f"{g}|{ci}|{mk}": est(lambda r, g=g, ci=ci, mk=mk: r["arm"] == "bare" and r["grade"] == g and r["ci"] == ci and mod(mk)(r))
                                      for g in LEVELS for ci in ("excludes null", "includes null") for mk in ["pooled"]}
st = Counter()
for r in rows:
    if r["labels"] and r["arm"] == "bare":
        st[f"{r['grade']}|{r['ci']}|{r['labels']['stance']}"] += 1
res["stance_vs_ci_bare"] = dict(sorted(st.items()))

# ---------------------------------------------------------------- exploratory: all-request bounds
allreq = {}
for mk in list(MODELS) + ["pooled"]:
    sub = [r for r in rows if r["arm"] == "bare" and low(r) and mod(mk)(r)]
    k = sum(r["binary"] == "yes" for r in sub); unk = sum(r["binary"] in ("gen_missing", "judge_missing") for r in sub)
    allreq[mk] = {"observed_yes_over_all": round(k / len(sub), 3), "upper_if_unknown_yes": round((k + unk) / len(sub), 3), "n_all": len(sub)}
res["exploratory_all_request_bounds_primary"] = allreq

# ---------------------------------------------------------------- exploratory: paired transitions
pairs = {}
idx = {(r["claim"], r["model"], r["arm"], r["prompt"]): r for r in rows}
for name, key_a, key_b in (("operator_vs_neutral", lambda c, m, a: (c, m, a, "neutral"), lambda c, m, a: (c, m, a, "operator")),
                           ("evidence_vs_bare", lambda c, m, p: (c, m, "bare", p), lambda c, m, p: (c, m, "evidence", p))):
    tr = Counter()
    for c in claims:
        for m in MODELS:
            for z in (ARMS if name == "operator_vs_neutral" else PROMPTS_):
                a, b = idx[key_a(c, m, z)]["binary"], idx[key_b(c, m, z)]["binary"]
                if a in ("yes", "no") and b in ("yes", "no"):
                    tr[f"{claims[c]['grade']}|{a}->{b}"] += 1
    pairs[name] = dict(sorted(tr.items()))
res["exploratory_paired_transitions"] = pairs

# ---------------------------------------------------------------- exploratory: leave-one-review-out (primary pooled)
loo = []
for rv in REVS:
    p, n, _ = prop([r for r in rows if r["review"] != rv and r["arm"] == "bare" and low(r)])
    if p is not None: loo.append((round(p, 3), rv))
res["exploratory_loo_primary_pooled"] = {"min": min(loo), "max": max(loo)} if loo else None

# ---------------------------------------------------------------- controls
ctrl = {}
for r in read_jsonl(OUT / "judge_controls.jsonl"): ctrl[r["item"]] = lab(r)
cres = []
for p in read_jsonl(CONTROLS):
    a, b = ctrl.get(p["pair_id"] + "/a"), ctrl.get(p["pair_id"] + "/b")
    if not a or not b:
        ok = strict = None
    elif p["kind"] == "epistemic":
        ok = strict = binary_outcome(a) == "yes" and binary_outcome(b) == "no"
    else:
        ok = binary_outcome(a) == binary_outcome(b)   # registered: identical binary
        strict = ok and all(a[k] == b[k] for k in ("stance", "commitment", "evidence_reservation")) and a["clinical_prudence"] == "absent" and b["clinical_prudence"] == "present"
    cres.append({"pair": p["pair_id"], "type": p["type"], "kind": p["kind"], "ok": ok, "strict": strict,
                 "a": a, "b": b, "binary_a": binary_outcome(a) if a else None, "binary_b": binary_outcome(b) if b else None})
res["controls"] = {"epistemic_ok": sum(1 for c in cres if c["kind"] == "epistemic" and c["ok"]), "epistemic_n": sum(c["kind"] == "epistemic" for c in cres),
                   "hedge_ok": sum(1 for c in cres if c["type"] == "hedge" and c["ok"]), "evidence_ok": sum(1 for c in cres if c["type"] == "evidence" and c["ok"]),
                   "prudence_ok": sum(1 for c in cres if c["kind"] == "prudence" and c["ok"]), "prudence_strict_ok": sum(1 for c in cres if c["kind"] == "prudence" and c["strict"]),
                   "prudence_n": sum(c["kind"] == "prudence" for c in cres), "detail": cres}

# ---------------------------------------------------------------- judge diagnostics (final records only)
fin = [judged[r["call_id"]] for r in rows if r["call_id"] in judged]
qs = [v for j in fin if j.get("quote_found") for v in j["quote_found"].values() if v is not None]
res["judge_quotes_found_normalized_substring"] = [sum(qs), len(qs)]
res["judge_parse_errors_final"] = sum(1 for j in fin if j.get("parse_error"))
res["median_words"] = {mk: statistics.median([r["words"] for r in rows if r["model"] == mk and r["words"] is not None])
                       for mk in MODELS if any(r["model"] == mk and r["words"] for r in rows)}

# ---------------------------------------------------------------- human agreement (if MP annotated)
mp_csv, mp_map = A_DIR / "sheets" / "mp_blind_ans.csv", A_DIR / "private" / "mp_map.json"
if mp_csv.exists() and mp_map.exists():
    mp_rows = [x for x in csv.DictReader(open(mp_csv)) if x.get("stance")]
    mapping = json.loads(mp_map.read_text()); pairs_h = []
    for x in mp_rows:
        L = {k: x[k].strip() for k in ("scope", "refusal", "stance", "commitment", "evidence_reservation", "clinical_prudence")}
        jr = judged.get(mapping[x["item"]])
        if jr and lab(jr): pairs_h.append((binary_outcome(L), binary_outcome(lab(jr)), x["item"], L, lab(jr)))
    if pairs_h:
        n = len(pairs_h); agree = sum(a == b for a, b, *_ in pairs_h)
        cats = sorted({a for a, *_ in pairs_h} | {b for _, b, *_ in pairs_h})
        po = agree / n; pe = sum((sum(a == c for a, *_ in pairs_h) / n) * (sum(b == c for _, b, *_ in pairs_h) / n) for c in cats)
        res["human_agreement"] = {"n": n, "agree": agree, "percent": round(po, 3), "kappa": None if pe == 1 else round((po - pe) / (1 - pe), 3),
                                  "confusion": dict(Counter(f"MP={a}|judge={b}" for a, b, *_ in pairs_h)),
                                  "per_dimension_agreement": {d: round(sum(L[d] == J[d] for *_, L, J in pairs_h) / n, 3) for d in pairs_h[0][3]},
                                  "disagreements": [i for a, b, i, *_ in pairs_h if a != b]}

(OUT / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, allow_nan=False))
json.dump(rows, open(OUT / "rows.json", "w"), ensure_ascii=False)

# ---------------------------------------------------------------- exploratory: judge-free lexical markers
import re as _re
EVR = _re.compile(r"\b(evidence|data|research|studies|study|trials?)\b[^.]{0,60}\b(limited|weak|uncertain|low|very low|inconsistent|small|few|insufficient|sparse|mixed|imprecise|not (strong|conclusive|clear))\b|\b(low|very low|moderate)[- ](certainty|quality)\b|\bmore research\b|\b(uncertain|unclear|not clear|can'?t tell|cannot tell|not known|unknown)\b|\brisk of bias\b|\bimprecis", _re.I)
HEDGE1 = _re.compile(r"\b(may|might|could|probably|likely|possibly|appears?|seems?|suggests?)\b", _re.I)
lex = {}
for arm in ARMS:
    for mk in MODELS:
        for g in LEVELS:
            sub = [r for r in rows if r["arm"] == arm and r["model"] == mk and r["grade"] == g and r["call_id"] in gen]
            if not sub: continue
            txt = [gen[r["call_id"]]["text"] for r in sub]
            first = [(_re.split(r"(?<=[.!?])\s", t.strip(), maxsplit=1) or [""])[0] for t in txt]
            lex[f"{arm}|{mk}|{g}"] = {"n": len(sub), "uncertainty_or_evidence_language": round(sum(bool(EVR.search(t)) for t in txt) / len(sub), 3),
                                     "hedge_in_first_sentence": round(sum(bool(HEDGE1.search(t)) for t in first) / len(sub), 3),
                                     "mentions_grade_word": round(sum(bool(_re.search(r"\bGRADE\b|certainty", t)) for t in txt) / len(sub), 3)}
res["exploratory_lexical"] = lex

# ---------------------------------------------------------------- exploratory: second judge (GPT-6 Astra) agreement
j2p = OUT / "judge2_generation.jsonl"
if j2p.exists():
    j2 = {}
    for r in read_jsonl(j2p): j2[r["item"]] = r
    pr = [(binary_outcome(lab(judged[k])), binary_outcome(lab(v)), idx_m) for k, v in j2.items()
          if lab(v) and k in judged and lab(judged[k]) for idx_m in [k.rsplit("/", 1)[1]]]
    def kap(pp):
        n = len(pp)
        if not n: return None
        po = sum(a == b for a, b, _ in pp) / n; cats = {a for a, *_ in pp} | {b for _, b, _ in pp}
        pe = sum((sum(a == c for a, *_ in pp) / n) * (sum(b == c for _, b, _ in pp) / n) for c in cats)
        return {"n": n, "agree": round(po, 3), "kappa": None if pe == 1 else round((po - pe) / (1 - pe), 3),
                "argon_yes": sum(a == "yes" for a, *_ in pp), "astra_yes": sum(b == "yes" for _, b, _ in pp)}
    res["exploratory_judge2"] = {"all": kap(pr), **{MODELS[m]: kap([x for x in pr if x[2] == m]) for m in MODELS}}

# ---------------------------------------------------------------- exploratory: third judge (Claude Opus 5.5 high), added after primary results
j3p = OUT / "judge3_generation.jsonl"
if j2p.exists() and j3p.exists():
    j3 = {}
    for r in read_jsonl(j3p): j3[r["item"]] = r
    def pairs(ref, other):  # ref: dict item->labels; other: judge records
        return [(binary_outcome(ref[k]), binary_outcome(lab(v)), k.rsplit("/", 1)[1]) for k, v in other.items()
                if lab(v) and k in ref and ref[k]]
    def ren(d, a, b):
        return None if d is None else {**{k: v for k, v in d.items() if not k.endswith("_yes")}, a: d["argon_yes"], b: d["astra_yes"]}
    argon = {k: lab(judged[k]) for k in judged}
    astra = {k: lab(v) for k, v in j2.items()}
    out3 = {}
    for name, ref, a in (("opus_vs_argon", argon, "argon_yes"), ("opus_vs_astra", astra, "astra_yes")):
        pp = pairs(ref, j3)
        out3[name] = {"all": ren(kap(pp), a, "opus_yes"), **{MODELS[m]: ren(kap([x for x in pp if x[2] == m]), a, "opus_yes") for m in MODELS}}
    # cross-family check: each evaluated model judged by the judge from neither its own family nor the primary one
    out3["n_items"] = len(j3); out3["n_parse_errors"] = sum(1 for v in j3.values() if v.get("parse_error"))
    res["exploratory_judge3"] = out3
(OUT / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, allow_nan=False))

# ---------------------------------------------------------------- results.md (compact)
f = lambda e: "n/a" if e["p"] is None else f"{e['yes']}/{e['eligible']} = {e['p']:.2f} [{e['ci95'][0]}, {e['ci95'][1]}]"
md = ["# Experiment A results (generated by src/analyze.py)", "", f"Audit: {res['audit']}", "",
      "## Primary (question only, low + very low)", "", "| Model | yes/eligible = share [95% cluster CI] | claims | reviews | na | missing |", "|---|---|---|---|---|---|"]
for mk in list(MODELS) + ["pooled"]:
    e = res["primary_bare_low_verylow"][mk]
    md.append(f"| {MODELS.get(mk, 'Pooled')} | {f(e)} | {e['claims']} | {e['reviews']} | {e['na']} | {e['missing']} |")
md += ["", "## By GRADE level", "", "| Arm | Model | High | Moderate | Low | Very low |", "|---|---|---|---|---|---|"]
for arm in ARMS:
    for mk in list(MODELS) + ["pooled"]:
        md.append(f"| {arm} | {MODELS.get(mk, 'Pooled')} | " + " | ".join(f(res['by_level'][f'{arm}|{mk}|{g}']) for g in LEVELS) + " |")
md += ["", "## Secondary contrasts (difference in share, 95% cluster CI)", ""] + [f"- {k}: {v['diff']} {v['ci95']}" for k, v in sec.items()]
c = res["controls"]
md += ["", f"## Controls: epistemic {c['epistemic_ok']}/{c['epistemic_n']} (hedge {c['hedge_ok']}/6, evidence {c['evidence_ok']}/6); prudence binary-invariant {c['prudence_ok']}/{c['prudence_n']} (strict {c['prudence_strict_ok']})",
       "", f"Claims GRADE x CI: {res['claims_grade_x_ci']}", "", f"Human agreement: {res.get('human_agreement', 'not available')}", "", f"Second judge (exploratory): {res.get('exploratory_judge2', 'not available')}", "", f"Third judge (exploratory): {res.get('exploratory_judge3', 'not available')}"]
(OUT / "results.md").write_text("\n".join(md) + "\n")

# ---------------------------------------------------------------- figure
# Paper style: sans-serif 8-9 pt, 6.5 in text width, Okabe-Ito palette, no in-image titles.
MODEL_STYLE = {"evaluated_1": ("#0072B2", "o"), "evaluated_2": ("#D55E00", "s")}
LEVEL_LABELS = ["High", "Moderate", "Low", "Very low"]
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "legend.fontsize": 8, "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.major.size": 3, "ytick.major.size": 3, "axes.edgecolor": "#333333",
        "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "pdf.fonttype": 42, "ps.fonttype": 42})

    def _style_y(ax):
        ax.set_ylim(-0.02, 1.02); ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        ax.grid(axis="y", color="#dddddd", lw=0.5); ax.set_axisbelow(True)
        ax.set_xticks(range(4)); ax.set_xticklabels(LEVEL_LABELS); ax.tick_params(axis="x", length=0)

    (A_DIR / "figures").mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.6), sharey=True)
    for ax, arm in zip(axes, ARMS):
        ax.axvspan(1.5, 3.5, color="#e8e8e8", alpha=0.6, lw=0, zorder=0)
        for off, mk in zip((-0.09, 0.09), ("evaluated_1", "evaluated_2")):
            col, mkr = MODEL_STYLE[mk]
            es = [res["by_level"][f"{arm}|{mk}|{g}"] for g in LEVELS]
            xs = [i + off for i in range(4)]
            ys = [e["p"] if e["p"] is not None else float("nan") for e in es]
            lo = [y - e["ci95"][0] if e["ci95"][0] is not None else 0 for y, e in zip(ys, es)]
            hi = [e["ci95"][1] - y if e["ci95"][1] is not None else 0 for y, e in zip(ys, es)]
            ax.errorbar(xs, ys, yerr=[lo, hi], marker=mkr, ms=4.5, color=col, mec="white", mew=0.6,
                        label=MODELS[mk], capsize=2, elinewidth=0.9, capthick=0.9, lw=1.1, zorder=3)
        _style_y(ax); ax.set_xlim(-0.5, 3.5)
        ax.text(2.5, 1.0, "primary range", ha="center", va="bottom", fontsize=7, color="#666666",
                transform=ax.get_xaxis_transform())
        ax.set_title("Question only" if arm == "bare" else "Question + evidence summary", pad=10)
        ax.set_xlabel("GRADE certainty")
    axes[0].set_ylabel("Categorical, no evidence caveat")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.08), handletextpad=0.4, columnspacing=1.5)
    fig.tight_layout(w_pad=1.2)
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        fig.savefig(A_DIR / "figures" / f"fig1_by_grade.{ext}", **kw)
    plt.close(fig)
except Exception as e:
    print("figure skipped:", e)
print((OUT / "results.md").read_text())

# ---------------------------------------------------------------- figure 2: components by level (question only)
try:
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 2.6), sharey=True)
    cats = [("categorical, no caveat", "#E69F00"), ("categorical + evidence caveat", "#F5D08E"),
            ("reserved (hedged)", "#A6D0EC"), ("unresolved", "#3E8DC4"), ("out of scope / refusal", "#C8C8C8")]
    for ax, mk in zip(axes, MODELS):
        bottoms = [0] * 4
        for name, col in cats:
            vals = []
            for g in LEVELS:
                sub = [r for r in rows if r["arm"] == "bare" and r["model"] == mk and r["grade"] == g and r["labels"]]
                def cls(L):
                    if L["scope"] != "in_scope" or L["refusal"] != "answers": return "out of scope / refusal"
                    if L["stance"] == "unresolved": return "unresolved"
                    if L["commitment"] == "reserved": return "reserved (hedged)"
                    return "categorical, no caveat" if L["evidence_reservation"] == "absent" else "categorical + evidence caveat"
                vals.append(sum(cls(r["labels"]) == name for r in sub) / len(sub) if sub else 0)
            ax.bar(range(4), vals, bottom=bottoms, color=col, label=name, width=0.62, edgecolor="white", linewidth=0.5, zorder=2)
            bottoms = [b + v for b, v in zip(bottoms, vals)]
        _style_y(ax); ax.set_xlim(-0.5, 3.5)
        ax.set_title(MODELS[mk], color=MODEL_STYLE[mk][0])
        ax.set_xlabel("GRADE certainty")
    axes[0].set_ylabel("Share of responses")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.08),
               handlelength=1.0, handletextpad=0.4, columnspacing=1.0, fontsize=7.5)
    fig.tight_layout(w_pad=1.2)
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        fig.savefig(A_DIR / "figures" / f"fig2_components.{ext}", **kw)
    plt.close(fig)
except Exception as e:
    print("figure 2 skipped:", e)
