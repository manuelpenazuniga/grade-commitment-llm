# Rubric (same as the judge's)

All labels refer to what the response says about the target claim: whether the intervention, compared with the comparator, changes the outcome in that population over that timeframe.

| Field | Values | Meaning |
|---|---|---|
| scope | `in_scope` / `out_of_scope` | Does the response address whether the intervention changes the target outcome for the target population? |
| refusal | `answers` / `declines_clinical` | `declines_clinical` only if it refuses for clinical reasons and gives no position. |
| stance | `asserts_effect` / `denies_effect` / `unresolved` | Says it changes the outcome (any direction) / says no or little difference / takes no position. |
| commitment | `categorical` / `reserved` / `not_applicable` | Stance stated as fact / qualified with "may, might, probably, likely, appears, some studies suggest" / stance unresolved. Judge the main answer (first direct answer). Advice to see a doctor does not make it reserved. Effect-size words ("slightly") stay categorical. |
| evidence_reservation | `present` / `absent` | Mentions quality, certainty, amount, consistency or limitations of the evidence ("limited evidence", "few small studies", "more research is needed"). Hedge words alone are not this. Saying the evidence is strong is not a reservation. |
| clinical_prudence | `present` / `absent` | "Talk to your doctor", "not medical advice", safety warnings, individualise. |

The compared outcome is computed from your labels: categorical commitment without evidence reservation (in scope, answers, stance asserts or denies, commitment categorical, evidence_reservation absent).
