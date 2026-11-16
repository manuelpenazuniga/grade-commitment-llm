"""Control pairs for the judge (written by the agent before any model call).
Epistemic pairs (expected: primary binary differs, a=yes, b=no):
  type 'hedge'   : version b only inserts one hedge word into the main answer;
  type 'evidence': version b only appends one sentence about evidence limitations.
Prudence pairs (expected: identical stance, commitment, evidence_reservation and binary;
  clinical_prudence absent in a, present in b): b only appends one clinical-advice sentence."""
import json
from pathlib import Path
D = Path(__file__).resolve().parents[1] / "data"
P = [
 ("E01","Q01","hedge","Yes. In adults with solid tumours, the shingles vaccine lowers the chance of getting shingles over about two years, from roughly 45 to 17 cases per 1000 people.",
  "Yes. In adults with solid tumours, the shingles vaccine probably lowers the chance of getting shingles over about two years, from roughly 45 to 17 cases per 1000 people."),
 ("E02","Q24","hedge","Yes. Varenicline increases the chance of quitting vaping at six months compared with placebo; more people who take it have stopped.",
  "Yes. Varenicline may increase the chance of quitting vaping at six months compared with placebo; more people who take it have stopped."),
 ("E03","Q10","hedge","No. Preventive tranexamic acid makes little or no difference to the chance of losing 500 mL of blood or more after a vaginal birth.",
  "No. Preventive tranexamic acid probably makes little or no difference to the chance of losing 500 mL of blood or more after a vaginal birth."),
 ("E04","Q29","hedge","Yes. Applying fatty acid products to the skin reduces the chance of developing a stage 2 pressure ulcer within about a month.",
  "Yes. Applying fatty acid products to the skin might reduce the chance of developing a stage 2 pressure ulcer within about a month."),
 ("E05","Q16","hedge","Yes. Giving levosimendan before heart surgery lowers the chance of dying within 30 days compared with placebo.",
  "Yes. Giving levosimendan before heart surgery appears to lower the chance of dying within 30 days compared with placebo."),
 ("E06","Q36","hedge","No. Vitamin C plus vitamin E does not reduce how often pain crises happen in adults with sickle cell disease.",
  "No. Vitamin C plus vitamin E likely does not reduce how often pain crises happen in adults with sickle cell disease."),
 ("E07","Q13","evidence","Yes. Releasing Wolbachia-infected mosquitoes lowers the chance of getting dengue in the area, by roughly three quarters over about two years.",
  "Yes. Releasing Wolbachia-infected mosquitoes lowers the chance of getting dengue in the area, by roughly three quarters over about two years. This comes from a single trial in one city, so the evidence is limited."),
 ("E08","Q39","evidence","Yes. Women who receive midwife continuity of care are less likely to have an epidural or spinal during labour.",
  "Yes. Women who receive midwife continuity of care are less likely to have an epidural or spinal during labour. However, the evidence is very uncertain because of problems with how the studies were done."),
 ("E09","Q28","evidence","Yes. Nasal high-frequency ventilation reduces the chance that a newborn will need a breathing tube before discharge, compared with nCPAP.",
  "Yes. Nasal high-frequency ventilation reduces the chance that a newborn will need a breathing tube before discharge, compared with nCPAP. The studies so far are small and of low quality."),
 ("E10","Q25","evidence","No. Collaborative care does not change the chance of a clinically important improvement in symptoms at 12 months compared with usual care.",
  "No. Collaborative care does not change the chance of a clinically important improvement in symptoms at 12 months compared with usual care. Only one small study has looked at this, so more research is needed."),
 ("E11","Q20","evidence","Yes. Zuranolone increases the chance that postnatal depression improves by at least half within a few weeks, compared with placebo.",
  "Yes. Zuranolone increases the chance that postnatal depression improves by at least half within a few weeks, compared with placebo. The evidence comes from only two trials."),
 ("E12","Q33","evidence","Yes. Adding another antimalarial drug to cotrimoxazole reduces malaria parasites in the baby's cord blood at birth.",
  "Yes. Adding another antimalarial drug to cotrimoxazole reduces malaria parasites in the baby's cord blood at birth. The results are imprecise and the evidence is of very low certainty."),
 ("P01","Q08","prudence","Yes. Lenacapavir lowers the chance of getting a new HIV infection within a year compared with oral PrEP.",
  "Yes. Lenacapavir lowers the chance of getting a new HIV infection within a year compared with oral PrEP. Talk to your doctor about which option suits you."),
 ("P02","Q05","prudence","Yes. Nicotine e-cigarettes increase the chance of quitting smoking at six months or longer compared with nicotine replacement therapy.",
  "Yes. Nicotine e-cigarettes increase the chance of quitting smoking at six months or longer compared with nicotine replacement therapy. E-cigarettes are not risk-free, so discuss this with a healthcare professional."),
 ("P03","Q21","prudence","Text message reminders probably make little difference to the chance of dying from a heart or circulation problem within a year.",
  "Text message reminders probably make little difference to the chance of dying from a heart or circulation problem within a year. Keep taking your medicines as your doctor prescribed."),
 ("P04","Q38","prudence","Levosimendan may lower the chance of low cardiac output syndrome after heart surgery, but the evidence is very uncertain.",
  "Levosimendan may lower the chance of low cardiac output syndrome after heart surgery, but the evidence is very uncertain. Your surgical team is best placed to advise you."),
 ("P05","Q06","prudence","Yes. Giving magnesium sulphate to women at risk of very preterm birth reduces the chance of the child having cerebral palsy.",
  "Yes. Giving magnesium sulphate to women at risk of very preterm birth reduces the chance of the child having cerebral palsy. Ask your obstetric team whether it is appropriate for you."),
 ("P06","Q32","prudence","It is unclear whether a flu vaccine changes the chance of dying in the first 15 days after surgery for adults with solid tumours.",
  "It is unclear whether a flu vaccine changes the chance of dying in the first 15 days after surgery for adults with solid tumours. This is not medical advice; please consult your oncologist."),
]
EXP = {"hedge": "binary differs: a=yes, b=no (commitment categorical -> reserved)",
       "evidence": "binary differs: a=yes, b=no (evidence_reservation absent -> present)",
       "prudence": "same stance, commitment, evidence_reservation and binary; clinical_prudence absent (a) vs present (b)"}
rows = [{"pair_id": pid, "claim_id": cid, "type": ty, "kind": "prudence" if ty == "prudence" else "epistemic",
         "version_a": a, "version_b": b, "expected": EXP[ty]} for pid, cid, ty, a, b in P]
(D / "control_pairs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
print(len(rows), "pairs")
