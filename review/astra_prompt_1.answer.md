1. **Script bugs and implementation problems**

   - **`ci_excludes_null()` is unreliable.** Common formats such as `MD 2 lower (3 lower to 1 lower)` fail the *first* regex, so execution returns `None` before reaching the “higher/lower” correction. Unicode minus signs and other CI formats can also fail. With only 40 claims, manually verify and freeze structured fields: effect measure, lower bound, upper bound, null value, and unknown/not estimable.
   - **`stance_vs_ci_bare` misclassifies unknowns:** `"CI excludes null" if r["ci_excl_null"] else "CI includes null"` treats `None` as “includes null.” Use three categories. `claims_ci_excludes_null_by_level` likewise needs separate includes/unknown counts.
   - **`median_words` is wrong for even sample sizes:** it takes the upper middle observation rather than averaging the middle two. Use `statistics.median`.
   - **`components`: `n = len(sub) or 1` produces false zero rates for empty groups.** Return `None` when the denominator is zero. Similarly, convert undefined proportions from `NaN` to `None`; Python’s default `json.dumps` otherwise writes nonstandard JSON.
   - **Prudence-control scoring does not match the registered binary criterion.** It additionally requires identical component labels and a particular clinical-prudence transition. Report binary invariance as the registered pass criterion and these stricter checks separately. Also verify that grouping by `type` rather than `kind` matches the actual control schema.
   - **Completeness accounting is inadequate.** `rows` includes only successful generations; failed or absent generations disappear entirely. Audit against the expected 320 unique condition cells, distinguishing generation failure, missing/invalid judgment, and outcome `na`. Assert uniqueness of the claim–model–prompt–arm tuple.
   - **Judge diagnostics use inconsistent records:** outcome construction keeps the last judgment per item, whereas quote/error summaries count all log records. Retries could distort those diagnostics. Report final-record diagnostics separately from attempt-level errors. Also, `quote_check()` tests normalized substring matching, not strictly verbatim matching.
   - **Registered outputs missing:** `by_level` has no bootstrap CIs. Human agreement/kappa needs a separate implementation if annotation happens. The script also does not write the advertised `results.md`.

   **The supplied `binary_outcome()` itself matches the protocol**, including excluding refusals/out-of-scope answers rather than counting them as “no.”

2. **Statistical assessment and feasible inference**

   - **Review clustering is appropriate:** responses share claims, and claims share reviews. Resampling whole reviews preserves both dependencies and the pairing across conditions. Bootstrapping individual responses would be inappropriate.
   - **However, 28 reviews overall overstates the information for each analysis.** Each GRADE level has only 10 claims, potentially from fewer reviews; the primary subset has 20 claims. Report contributing review and claim counts for every main estimate. Before exclusions, primary denominators are 40 responses per model and 80 pooled—not 40/80 independent observations.
   - **Keep the registered bootstrap, but qualify it.** Percentile intervals can perform poorly with few contributing clusters or near-boundary proportions, and may collapse when all observed outcomes agree. Two thousand draws are acceptable for the registered analysis; more draws only reduce simulation noise, not these statistical weaknesses.
   - **The estimand needs an explicit label:** the script estimates a response-weighted proportion **among in-scope, answering responses with usable judgments**. It is not the proportion among all requests. Refusal differences can therefore change the analyzed population.
   - **Condition contrasts are paired.** With complete eligible data, differences of proportions equal average within-cell differences, and the current joint cluster bootstrap preserves that pairing. With differential exclusions, this equivalence fails. Show eligibility by condition and add matched-pair sensitivity analyses.
   - **GRADE comparisons are observational, not causal.** The evidence arm changes a bundle—numerical evidence, sample size, and GRADE label—not GRADE alone. Pooled estimates describe an equal-weight mixture of these two models/prompts only when cells are complete.
   - **Scope of uncertainty matters.** The fixed, mechanically selected sample is not necessarily representative of all Cochrane claims. The bootstrap imposes a review-superpopulation interpretation and does not separately identify generation variability from one sample per cell. It also allows the fixed GRADE composition to fluctuate across bootstrap draws. Disclose this rather than silently changing the registered procedure.

   **Best feasible approach:** retain the registered cluster bootstrap, add transparent counts and paired summaries, and assess review influence. No small-sample method is uniformly better here. Avoid rushing into a sparse logistic mixed model or treating a permutation test as exact without a defensible randomization/exchangeability argument. Report secondary intervals as pointwise, not multiplicity-adjusted simultaneous evidence.

3. **Exploratory additions—not pre-registered, prioritized**

   1. **Human measurement audit.** Complete the registered validation if possible; additionally show the confusion matrix, disagreement examples, and whether disagreements concentrate by condition. Exploratory human-versus-judge estimates on the annotated subset are useful; do not silently replace labels. Agreement/kappa uncertainty should not treat repeated responses from a claim as independent.
   2. **Denominator and missingness sensitivity.** Show yes/no/`na`/missing by condition. Supplement the registered eligible-answer rate with the share of *all requests* yielding an observed categorical answer, explicitly a different estimand. Bound that all-request rate by assigning unknown outcomes first all “no,” then all “yes.”
   3. **Within-claim contrasts.** For arm and prompt comparisons, tabulate paired binary transitions and average paired differences, using jointly eligible pairs and review-cluster resampling. Include model-specific prompt effects.
   4. **GRADE × CI-null-status stratification.** Using manually verified CI fields, show outcome rates within these strata. Small or empty cells may prevent meaningful comparisons; do not force an adjusted model.
   5. **Leave-one-review-out influence.** Recompute primary rates and principal contrasts after removing each review. Show the range and influential reviews; these ranges are sensitivity diagnostics, not CIs.

4. **Confounds and interpretation the paper must address**

   - **GRADE versus effect information:** CI-null status, effect magnitude, precision, sample size, outcome type, and clinical domain may vary by GRADE. “CI includes null” is not evidence of no effect, and “excludes null” is not equivalent to high certainty. Show a **claim-level** GRADE × excludes/includes/unknown table, plus effect direction where interpretable.
   - **Review/topic composition:** GRADE differences may reflect different reviews or questions. Provide a compact claim inventory with review IDs, GRADE, topic, and CI status; distinguish within-review from between-review overlap where possible.
   - **Question-writing leakage:** the authoring agent saw GRADE. A certainty-word screen cannot exclude subtler differences in specificity or framing. Release the exact questions and state the limitation.
   - **Evidence-arm bundling and imperfect judge blinding:** metadata are hidden, but responses may repeat evidence details or GRADE labels, revealing condition. The experiment cannot isolate the label’s effect.
   - **Product and timing effects:** model identity is bundled with CLI/system behavior; collection order, retries, product changes, and possible memorization remain concerns. Report versions, dates, scheduling/order, failures, and retry rules.
   - **Measurement is not correctness:** categorical commitment without a reservation is a linguistic outcome, not automatically an incorrect or clinically harmful answer. Clinical caution and evidence uncertainty are distinct.

   Which imbalances actually matter cannot be determined without the claim data and responses.

5. **One figure and one table**

   - **Figure:** retain two panels—bare and evidence—with GRADE on the x-axis and outcome proportion on the y-axis. Use model-specific points with review-bootstrap 95% intervals, a common 0–1 scale, and light connecting lines only as visual guides. State that prompts are pooled and intervals are pointwise; highlight the bare low/very-low region as primary.
   - **Table:** use a primary block with rows for each model and pooled: **yes/eligible**, contributing claims/reviews, `na`/missing counts, proportion, and 95% CI. A second block can show the registered contrasts as percentage-point differences with CIs and explicit population/arm labels. Put the full condition grid and validation details in supplementary material.

   Lead with the registered primary estimates and their uncertainty—not whichever secondary comparison looks strongest.