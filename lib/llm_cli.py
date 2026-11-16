"""Single invocation wrapper for the three subscription CLIs (claude, codex, agy).

Guarantees per call (verified before the experiment):
- fresh empty temporary working directory outside the repository;
- no tools, no file access, no web search, no previous session / resume;
- model pinned with an explicit option, reasoning effort pinned;
- system prompt replaced where the CLI allows it (all three do, with residues logged);
- user-level global instructions neutralised where possible, and their state logged;
- one JSONL record per call: CLI + version, exact argv, requested and declared model,
  full prompt, raw output, exit code, timestamps;
- resumable: a call_id already recorded with status "ok" is never repeated;
- one call at a time per CLI across processes (file lock) plus a minimum spacing;
- on a usage/rate limit: wait and retry with backoff; never burst.

The orchestrating agent never answers stimuli: every evaluated answer and every judgment
comes from a separate CLI process launched here.

Usage (library):
    from llm_cli import call
    rec = call(cli="codex", model="gpt-6.1-sol", prompt="...", system="...",
               effort="medium", call_id="A/gen/A01/neutral/codex", log_path=".../calls.jsonl")
    rec["text"]  # final answer text
"""
from __future__ import annotations

import datetime as _dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOCK_DIR = Path(tempfile.gettempdir()) / "llmcli_locks"
CODEX_ISO = Path(tempfile.gettempdir()) / "llmcli_codex_iso"  # isolated HOME/CODEX_HOME
MIN_SPACING_S = {"claude": 2.0, "codex": 2.0, "agy": 2.0}
CALL_TIMEOUT_S = 900
BACKOFF_S = [60, 180, 300, 600, 900, 1200]
RATE_PAT = re.compile(
    r"rate.?limit|usage limit|quota|RESOURCE_EXHAUSTED|too many requests|\b429\b|"
    r"limit reached|exceeded your|try again later|overloaded",
    re.I,
)
GLOBAL_INSTRUCTION_FILES = {
    "claude": ["~/.claude/CLAUDE.md"],
    "codex": ["~/.codex/AGENTS.md", "~/.codex/instructions.md"],
    "agy": ["~/.gemini/GEMINI.md", "~/.gemini/AGENTS.md"],
}


class RateLimitStop(RuntimeError):
    """Raised when a usage limit does not clear after the full backoff schedule."""


class IsolationViolation(RuntimeError):
    """Raised when a call used a tool (file, shell, web) despite the lockdown."""


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


_VERSION_CACHE: dict[str, str] = {}


def cli_version(cli: str) -> str:
    if cli not in _VERSION_CACHE:
        try:
            out = subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=60)
            _VERSION_CACHE[cli] = (out.stdout or out.stderr).strip().splitlines()[0]
        except Exception as e:  # pragma: no cover
            _VERSION_CACHE[cli] = f"unknown ({e})"
    return _VERSION_CACHE[cli]


def global_instruction_state(cli: str) -> dict:
    """Record size and hash of user-level instruction files (content is not credentials)."""
    state = {}
    for p in GLOBAL_INSTRUCTION_FILES[cli]:
        fp = Path(os.path.expanduser(p))
        if fp.exists():
            data = fp.read_text(errors="replace")
            state[p] = {"bytes": len(data.encode()), "sha": _sha(data), "content": data[:2000]}
        else:
            state[p] = None
    return state


# ----------------------------------------------------------------------------- builders
def _ensure_codex_iso() -> dict:
    """Isolated HOME and CODEX_HOME so no user config, skills, AGENTS.md or memories load.
    auth.json is symlinked, never read or copied."""
    home = CODEX_ISO / "home"
    chome = CODEX_ISO / "codex_home"
    home.mkdir(parents=True, exist_ok=True)
    chome.mkdir(parents=True, exist_ok=True)
    link = chome / "auth.json"
    if not link.is_symlink():
        link.symlink_to(Path(os.path.expanduser("~/.codex/auth.json")))
    return {"HOME": str(home), "CODEX_HOME": str(chome)}


CODEX_DISABLE = [
    "shell_tool", "unified_exec", "multi_agent", "multi_agent_v2", "apps", "plugins",
    "image_generation", "hooks", "browser_use", "browser_use_external", "computer_use",
    "view_image", "goals", "sleep_tool", "skill_search", "tool_suggest", "in_app_browser",
    "code_mode_host", "memories",
]


def _build(cli: str, model: str, prompt: str, system: str | None, effort: str, work: Path, aux: Path):
    env = dict(os.environ)
    # never let a nested CLI think it runs inside the orchestrating Claude Code session
    for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT"):
        env.pop(k, None)
    controls = {}
    if cli == "claude":
        argv = [
            "claude", "-p", prompt,
            "--model", model, "--effort", effort,
            "--tools", "",
            "--safe-mode", "--strict-mcp-config", "--disable-slash-commands",
            "--no-session-persistence",
            "--output-format", "json",
        ]
        if system is not None:
            argv += ["--system-prompt", system]
        controls = {
            "system_prompt": "replaced (--system-prompt); residue: fixed Agent-SDK identity line and an "
                             "auto-attached context block (environment, account email), ~630 tokens, not controllable",
            "tools": "none (--tools '')",
            "web": "no tool available",
            "reasoning": f"--effort {effort}",
            "temperature": "not exposed by CLI",
            "global_instructions": "--safe-mode (no CLAUDE.md, installed plugins, hooks, MCP); built-in plugins still load",
            "session": "--no-session-persistence",
        }
    elif cli == "codex":
        sysfile = aux / "system.txt"
        sysfile.write_text(system if system is not None else "")
        env.update(_ensure_codex_iso())
        argv = [
            "codex", "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
            "--ignore-rules", "-s", "read-only", "-C", str(work),
            "-m", model,
            "-c", f"model_reasoning_effort={effort}",
            "-c", f'model_instructions_file="{sysfile}"',
            "-c", 'web_search="disabled"',
            "-c", "project_doc_max_bytes=0",
            "-c", "include_permissions_instructions=false",
            "-c", "include_environment_context=false",
            "-c", "include_apps_instructions=false",
            "-c", "include_collaboration_mode_instructions=false",
            "--json",
        ]
        for f in CODEX_DISABLE:
            argv += ["--disable", f]
        argv += [prompt]
        controls = {
            "system_prompt": "replaced (model_instructions_file); residue: bundled system-skills list and "
                             "multi-agent role developer messages (product text, see REGISTRO)",
            "tools": "shell/exec/apps/plugins/browser/computer-use/image disabled; read-only sandbox",
            "web": 'web_search="disabled"',
            "reasoning": f"model_reasoning_effort={effort}",
            "temperature": "not exposed by CLI",
            "global_instructions": "isolated HOME and CODEX_HOME (no config.toml, AGENTS.md, user skills, memories)",
            "session": "--ephemeral",
        }
    elif cli == "agy":
        agents = work / ".agents" / "agents"
        agents.mkdir(parents=True)
        body = system if system is not None else ""
        (agents / "bare.md").write_text(
            "---\nname: bare\ndescription: Plain assistant with no tools.\nmainAgent: true\n"
            "excludeDefaultComponents: true\ntools: []\n---\n# bare\n" + body + "\n"
        )
        settings = {
            "allowNonWorkspaceAccess": False,
            "agentMode": "",
            "toolPermission": "strict",
            "permissions": {"deny": ["command(*)", "read_file(*)", "write_file(*)", "read_url(*)", "mcp(*)"]},
        }
        argv = [
            "agy", "-p", prompt, "--agent", "bare", "--model", model, "--effort", effort,
            "--output-format", "stream-json", "--print-timeout", f"{CALL_TIMEOUT_S - 30}s",
            "--disable-slash-commands", "--settings", json.dumps(settings),
        ]
        controls = {
            "system_prompt": "replaced (workspace custom agent, excludeDefaultComponents: true)",
            "tools": "built-in tools excluded by the agent; deny rules for command/read_file/write_file/read_url/mcp; "
                     "any tool step in the stream is treated as an isolation violation",
            "web": "search_web is NOT blockable by settings; excluded via the bare agent and audited per call",
            "reasoning": f"--effort {effort} (model id also carries an effort suffix)",
            "temperature": "not exposed by CLI",
            "global_instructions": "~/.gemini/GEMINI.md logged; default components excluded",
            "session": "new conversation per call (no --continue); conversations are persisted by agy",
        }
    else:
        raise ValueError(cli)
    return argv, env, controls


# ----------------------------------------------------------------------------- parsers
def _parse(cli: str, stdout: str) -> dict:
    out = {"text": None, "model_reported": None, "tool_events": [], "usage": None, "error": None}
    if cli == "claude":
        try:
            d = json.loads(stdout)
        except Exception:
            out["error"] = "unparseable json"
            return out
        d.pop("credential_expires_at", None)
        out["text"] = d.get("result")
        mu = d.get("modelUsage") or {}
        out["model_reported"] = ",".join(sorted(mu.keys())) or None
        stu = (d.get("usage") or {}).get("server_tool_use") or {}
        if any(stu.values()) or d.get("permission_denials") or (d.get("num_turns") or 1) > 1:
            out["tool_events"].append({"server_tool_use": stu, "permission_denials": d.get("permission_denials"),
                                       "num_turns": d.get("num_turns")})
        out["usage"] = d.get("usage")
        if d.get("is_error"):
            out["error"] = d.get("subtype") or "is_error"
        out["clean_stdout"] = json.dumps(d)
    elif cli == "codex":
        msgs = []
        for line in stdout.splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("type") == "item.completed":
                it = e.get("item", {})
                if it.get("type") == "agent_message":
                    msgs.append(it.get("text", ""))
                elif it.get("type") == "error":
                    out.setdefault("warnings", []).append(it.get("message"))
                elif it.get("type") not in ("reasoning",):
                    out["tool_events"].append(it)
            elif e.get("type") == "turn.completed":
                out["usage"] = e.get("usage")
            elif e.get("type") in ("error", "turn.failed"):
                out["error"] = json.dumps(e)[:500]
        out["text"] = msgs[-1] if msgs else None
    elif cli == "agy":
        for line in stdout.splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            ev = e.get("event")
            if ev == "init":
                out["model_reported"] = e["init"].get("model")
            elif ev == "step_update":
                st = e["step_update"].get("step_type")
                if st not in ("user_input", "agent_response", None):
                    out["tool_events"].append({"step_type": st})
            elif ev == "result":
                r = e["result"]
                out["text"] = r.get("response")
                out["usage"] = r.get("usage")
                if r.get("status") != "SUCCESS":
                    out["error"] = r.get("status")
        # de-duplicate step types
        seen = []
        for t in out["tool_events"]:
            if t not in seen:
                seen.append(t)
        out["tool_events"] = seen
    return out


# ----------------------------------------------------------------------------- log
def _load_done(log_path: Path) -> dict:
    done = {}
    if log_path.exists():
        for line in log_path.read_text().splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("status") == "ok":
                done[r["call_id"]] = r
    return done


def _append(log_path: Path, rec: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f, fcntl.LOCK_UN)


# ----------------------------------------------------------------------------- main entry
def call(cli: str, model: str, prompt: str, system: str | None, effort: str, call_id: str,
         log_path: str | Path, meta: dict | None = None, allow_tool_retry: int = 2) -> dict:
    """Run one isolated call; return the logged record. Cached if call_id already ok."""
    log_path = Path(log_path)
    done = _load_done(log_path)
    if call_id in done:
        return done[call_id]
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lockf = open(LOCK_DIR / f"{cli}.lock", "a+")
    attempt = 0
    tool_retries = 0
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX)  # one call at a time per CLI, across processes
        while True:
            # re-check after acquiring the lock (another process may have finished it)
            done = _load_done(log_path)
            if call_id in done:
                return done[call_id]
            stamp = LOCK_DIR / f"{cli}.last"
            if stamp.exists():
                wait = MIN_SPACING_S[cli] - (time.time() - stamp.stat().st_mtime)
                if wait > 0:
                    time.sleep(wait)
            base = Path(tempfile.mkdtemp(prefix="llmcli_"))
            work, aux = base / "work", base / "aux"
            work.mkdir()
            aux.mkdir()
            assert REPO not in work.resolve().parents, "temp dir must be outside the repo"
            argv, env, controls = _build(cli, model, prompt, system, effort, work, aux)
            t0 = _now()
            tic = time.time()
            try:
                p = subprocess.run(argv, cwd=work, env=env, capture_output=True, text=True,
                                   timeout=CALL_TIMEOUT_S, stdin=subprocess.DEVNULL)
                rc, so, se = p.returncode, p.stdout, p.stderr
            except subprocess.TimeoutExpired as e:
                rc, so, se = -9, (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "TIMEOUT"
            stamp.touch()
            dur = round(time.time() - tic, 2)
            parsed = _parse(cli, so)
            raw_stdout = parsed.pop("clean_stdout", so)
            warnings = parsed.pop("warnings", [])
            status = "ok"
            if parsed["tool_events"]:
                status = "tool_use"
            elif rc != 0 or parsed["error"] or not parsed["text"]:
                status = "error"
            rate_limited = status == "error" and bool(RATE_PAT.search((se or "") + (parsed["text"] or "") + (so or "")[-4000:]))
            rec = {
                "call_id": call_id,
                "status": status if not rate_limited else "rate_limited",
                "attempt": attempt + tool_retries,
                "ts_start": t0, "ts_end": _now(), "duration_s": dur,
                "cli": cli, "cli_version": cli_version(cli),
                "argv": argv,
                "env_overrides": {k: env[k] for k in ("HOME", "CODEX_HOME") if cli == "codex"},
                "cwd": str(work),
                "model_requested": model, "model_reported": parsed["model_reported"],
                "effort": effort,
                "controls": controls,
                "global_instructions": global_instruction_state(cli),
                "system_prompt": system, "prompt": prompt,
                "prompt_sha": _sha((system or "") + "\x00" + prompt),
                "exit_code": rc, "raw_stdout": raw_stdout, "raw_stderr": se[-5000:] if se else se,
                "text": parsed["text"], "usage": parsed["usage"],
                "tool_events": parsed["tool_events"], "error": parsed["error"], "warnings": warnings,
                "meta": meta or {},
            }
            _append(log_path, rec)
            shutil.rmtree(base, ignore_errors=True)
            if status == "ok":
                return rec
            if status == "tool_use":
                tool_retries += 1
                if tool_retries > allow_tool_retry:
                    raise IsolationViolation(f"{call_id}: tool use persisted ({parsed['tool_events'][:3]})")
                continue
            if rate_limited:
                blob = (se or "") + (parsed["text"] or "") + (so or "")[-4000:]
                m = re.search(r"resets\s+([A-Z][a-z]{2})\s+(\d{1,2})", blob)
                if m and _dt.datetime.now().strftime("%b") + " " + str(_dt.datetime.now().day) != f"{m.group(1)} {int(m.group(2))}":
                    raise RateLimitStop(f"{cli}/{model}: limit resets {m.group(1)} {m.group(2)}; not recoverable by waiting ({call_id})")
                if attempt >= len(BACKOFF_S):
                    raise RateLimitStop(f"{cli}: usage limit did not clear after backoff ({call_id})")
                time.sleep(BACKOFF_S[attempt])
                attempt += 1
                continue
            # generic error: retry twice with short pause, then give up (logged)
            attempt += 1
            if attempt > 2:
                return rec
            time.sleep(20)
    finally:
        fcntl.flock(lockf, fcntl.LOCK_UN)
        lockf.close()


if __name__ == "__main__":  # tiny CLI for smoke tests
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--system", default="You are a helpful assistant.")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--log", required=True)
    a = ap.parse_args()
    r = call(a.cli, a.model, a.prompt, a.system, a.effort, a.id, a.log)
    print(json.dumps({k: r[k] for k in ("call_id", "status", "model_reported", "text", "tool_events", "duration_s")},
                     ensure_ascii=False, indent=1))
    sys.exit(0 if r["status"] == "ok" else 1)
