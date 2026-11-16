import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from llm_cli import call
name, effort = sys.argv[1], sys.argv[2]
p = Path(__file__).parent / f"{name}.rendered.txt"
rec = call(cli="codex", model="gpt-6-astra", prompt=p.read_text(), system="You are a careful statistician and research methods advisor.",
           effort=effort, call_id=f"EA/consult/{name}", log_path=Path(__file__).parent / "calls.jsonl", meta={"topic": "EA", "step": "consultation"})
(Path(__file__).parent / f"{name}.answer.md").write_text(rec.get("text") or "")
print(rec["status"], rec.get("model_reported"), rec.get("error"))
