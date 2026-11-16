"""Fetch the candidate pool of open-access Cochrane reviews from PMC (E-utilities efetch,
batches of 20 ids, 1.5 s spacing). Saves one XML per article in data/raw/. Resumable."""
import json, sys, time, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
D = Path(__file__).resolve().parents[1] / "data"
RAW = D / "raw"; RAW.mkdir(parents=True, exist_ok=True)
ids = []
for y in ("2026", "2025", "2024"):
    ids += json.loads((D / f"esearch_{y}.json").read_text())["esearchresult"]["idlist"]
todo = [i for i in ids if not (RAW / f"PMC{i}.xml").exists()]
print(len(ids), "ids;", len(todo), "to fetch", flush=True)
for k in range(0, len(todo), 20):
    batch = todo[k:k + 20]
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(
        {"db": "pmc", "id": ",".join(batch), "rettype": "xml"})
    for attempt in range(3):
        try:
            data = urllib.request.urlopen(url, timeout=120).read(); break
        except Exception as e:
            print("retry", k, e, flush=True); time.sleep(5)
    else:
        print("FAILED batch", k); continue
    root = ET.fromstring(data)
    for art in root.iter("article"):
        pid = None
        for a in art.iter("article-id"):
            if a.get("pub-id-type") in ("pmc", "pmcid", "pmcaid"):
                pid = (a.text or "").replace("PMC", ""); break
        if pid:
            (RAW / f"PMC{pid}.xml").write_bytes(ET.tostring(art, encoding="utf-8"))
    print("batch", k, "ok", flush=True)
    time.sleep(1.5)
print("have", len(list(RAW.glob("*.xml"))))
