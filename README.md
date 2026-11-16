# Does the Answer Know How Good the Evidence Is?

Code, data and full call logs for the paper by Manuel Peña-Zúñiga, *"Does the Answer Know How Good the Evidence Is? Commitment of Commercial LLM Answers to Patient Questions Across GRADE Certainty Levels"*, submitted to the Apart Research AI x Epistemics Research Sprint (November 2026).

**Question.** When a patient asks an assistant whether a treatment works, does the commitment of the answer track the certainty of the evidence (GRADE) behind it?

**Design.** 40 patient questions built from Cochrane Summary-of-Findings rows (10 per GRADE level: high, moderate, low, very low; 28 reviews, 2024 to 2026), selected by a fixed rule that uses no model output. Fully crossed: 2 arms (question only, question plus evidence summary) x 2 system prompts (neutral, "concise and decisive" operator) x 2 models (GPT-6.1 Sol, Claude Sonnet 5.5) = 320 responses. An LLM judge from a third family (Gemini 4 Argon) labels each response with a fixed rubric. Inference is a review-level cluster bootstrap (B = 2000).

## Main results

| | Sol | Sonnet | Pooled |
|---|---|---|---|
| Categorical, no evidence caveat; low + very low; question only (**primary**) | 0/40 | 3/40 | 3/80 = 3.8% (95% CI 0 to 8.3) |
| Same, high certainty | 35% | 25% | 30% |
| High certainty, with evidence summary | 80% | 35% | 57.5% |
| Operator minus neutral prompt (question only) | | | +1.2 pp (-6.6 to 8.6) |

- Unqualified categorical answers on weak evidence are rare. The more common miscalibration is the reverse: answers on high-certainty evidence often carry evidence caveats, and moderate certainty is treated almost like low.
- Supplying the GRADE summary increases commitment only at high certainty.
- On very-low-certainty claims whose CI includes the null, 12 of 36 answers state that the treatment makes no difference.
- Judge validation: 10/12 epistemic and 6/6 prudence control pairs; the judge misses some single-word hedges, so the primary estimate is an upper bound. Exploratory second and third judges on a 96-response subsample: GPT-6 Astra 93/96 agreement with the primary judge (kappa 0.87); Claude Opus 5.5 94/96 (kappa 0.92); Astra vs Opus 95/96 (kappa 0.95). Each evaluated model is thus also judged by a model outside its family.

All numbers are produced by `src/analyze.py` from the logged outputs (`out/results.json`, `out/results.md`). Limitations are discussed in the paper (one sample per cell, 40 claims, GRADE confounded with CI status, LLM judge, no completed human annotation).

## Repository layout

```
PROTOCOL.md            frozen protocol (committed before the first evaluated-model call)
config/models.yaml     model identifiers, CLI and reasoning effort per role
data/
  esearch_*.json       PubMed Central search results (333 Cochrane review ids)
  sof_rows.jsonl       parsed Summary-of-Findings rows (1,297)
  candidates.jsonl     rows passing the selection rule
  question_fields.json lay population/intervention/comparison/outcome fields per claim
  ci_fields.json       hand-verified effect measure and CI bounds per claim
  claims.jsonl         the 40 claims, questions and evidence summaries (Q01 to Q40)
  control_pairs.jsonl  18 judge-validation pairs
prompts/               system prompts, user templates, judge rubric
src/
  fetch_pool.py        fetch review XML from PMC (spaced requests)
  sof_rows.py          parse SoF tables
  select_rows.py       fixed selection rule (seed 20261116)
  build_claims.py      build questions and evidence summaries
  make_pairs.py        build control pairs
  generate.py          evaluated-model calls
  judge.py             primary judge (controls and generations)
  judge2.py, judge3.py exploratory second and third judges on a 96-response subsample
  analyze.py           all estimates, CIs, figures
  make_mp_sheet.py     blind human-annotation sheet
lib/llm_cli.py         wrapper for the subscription CLIs (claude, codex, agy): tools disabled,
                       isolated config, one JSONL record per call
calls/                 raw logs of every model call: prompt, system prompt, argv, raw output, timing
out/                   parsed judge labels, results.json, results.md, rows.json
figures/               paper figures
sheets/                rubric and blank blind annotation sheet
review/                logged external review of the analysis plan (GPT-6 Astra)
```

## Reproducing

Analysis only (needs Python 3.11+, matplotlib for figures):

```
python -m venv .venv && .venv/bin/pip install matplotlib
.venv/bin/python src/analyze.py
```

Full pipeline: `src/fetch_pool.py` (downloads review XML into `data/raw/`, not redistributed), then `sof_rows.py`, `select_rows.py`, `build_claims.py`, `make_pairs.py`, `generate.py evaluated_1`, `generate.py evaluated_2`, `judge.py controls`, `judge.py generation`, `analyze.py`. Model calls require the `codex`, `claude` and `agy` CLIs logged in to their own subscriptions. Temperature is not exposed by these CLIs, so re-running generation will not reproduce the exact responses; the logged responses in `calls/` are the data analysed.

## Pre-registration and deviations

`PROTOCOL.md`, claims, prompts, rubric and control pairs were committed before any evaluated-model call. After an external review of the analysis plan (logged in `review/`) and before any judge output on the 320 responses was inspected, bugs in the analysis script were fixed and exploratory analyses were added. Every analysis not in the protocol is labelled exploratory in the code and in the paper. The third judge (Claude Opus 5.5) was added after the primary results were known.

## Data and licences

Claims are derived from open-access Cochrane reviews in PubMed Central; each claim records its review identifier. Full texts are not redistributed. Model outputs are included for research transparency. Code is released under the MIT licence.

## LLM usage

Claude Code (Claude Opus 5.5) wrote the pipeline and analysis code and helped draft the paper under the author's direction. Evaluated responses and judgments come only from the logged CLI calls in `calls/`.

## How to cite

Manuel Peña-Zúñiga (2026). *Does the Answer Know How Good the Evidence Is? Commitment of Commercial LLM Answers to Patient Questions Across GRADE Certainty Levels.* Apart Research AI x Epistemics Research Sprint. Code and data: https://github.com/manuelpenazuniga/grade-commitment-llm

```bibtex
@misc{penazuniga2026grade,
  author       = {Pe{\~n}a-Z{\'u}{\~n}iga, Manuel},
  title        = {Does the Answer Know How Good the Evidence Is? Commitment of Commercial {LLM} Answers to Patient Questions Across {GRADE} Certainty Levels},
  year         = {2026},
  howpublished = {Apart Research AI x Epistemics Research Sprint},
  url          = {https://github.com/manuelpenazuniga/grade-commitment-llm}
}
```

A machine-readable citation is in `CITATION.cff`.
