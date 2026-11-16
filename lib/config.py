"""Load config/models.yaml (roles -> cli, model, effort). Minimal parser, no dependencies.

Expected format (one role per line):
roles:
  evaluated_1: {cli: codex, model: gpt-6.1-sol, effort: medium, family: openai}
"""
from __future__ import annotations
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_roles(path: Path | None = None) -> dict:
    path = path or REPO / "config" / "models.yaml"
    if not path.exists():
        raise FileNotFoundError(f"{path} not written yet ")
    roles = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^\s{2}(\w+):\s*\{(.*)\}\s*(#.*)?$", line)
        if m:
            roles[m.group(1)] = {k.strip(): v.strip() for k, v in (kv.split(":", 1) for kv in m.group(2).split(","))}
    return roles
