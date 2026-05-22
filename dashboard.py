"""Dashboard for Claude Agent SDK session JSONL files.

Reads ~/.claude/projects/<encoded-cwd>/*.jsonl for the current project and
exposes a conversation explorer at /dashboard, with playback of any
TTS audio files written to voice_directory.
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse


# USD per million tokens. Approximate public pricing; surfaced as estimate only.
PRICING = {
    "opus":   {"in": 15.0,  "out": 75.0, "cache_write": 18.75, "cache_read": 1.50},
    "sonnet": {"in":  3.0,  "out": 15.0, "cache_write":  3.75, "cache_read": 0.30},
    "haiku":  {"in":  0.80, "out":  4.0, "cache_write":  1.00, "cache_read": 0.08},
}

# Window in which an audio file may have been written after an assistant turn finishes.
AUDIO_MATCH_WINDOW_S = 120.0

# Cache TTL for the global audio<->turn match (cheap to recompute, but no need every request).
_MATCH_CACHE: dict = {"at": 0.0, "by_session": None, "voice_dir": None, "project_dir": None}
_MATCH_TTL_S = 30.0


# ── helpers ────────────────────────────────────────────────────────────────

def _model_family(model: str) -> str | None:
    m = (model or "").lower()
    if "opus" in m:   return "opus"
    if "sonnet" in m: return "sonnet"
    if "haiku" in m:  return "haiku"
    return None


def _encode_cwd(cwd: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def _project_dir() -> Path:
    return Path.home() / ".claude" / "projects" / _encode_cwd(os.getcwd())


def _estimate_cost(model: str, usage: dict) -> float:
    fam = _model_family(model)
    if not fam or not usage:
        return 0.0
    p = PRICING[fam]
    return (
        usage.get("input_tokens", 0)                  * p["in"]          / 1e6
        + usage.get("output_tokens", 0)               * p["out"]         / 1e6
        + usage.get("cache_creation_input_tokens", 0) * p["cache_write"] / 1e6
        + usage.get("cache_read_input_tokens", 0)     * p["cache_read"]  / 1e6
    )


def _parse_ts(ts: str | None):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_audio_name(name: str) -> float | None:
    """Filename → epoch seconds (interpreting the naive local datetime as local time)."""
    base = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    for fmt in ("%Y-%m-%d_%H-%M-%S", "%Y-%m-%d %H%M%S.%f"):
        try:
            return datetime.strptime(base, fmt).timestamp()
        except ValueError:
            continue
    return None


def _is_real_user_content(content) -> bool:
    """True if a user message is a typed prompt, not a tool_result reply."""
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("type") == "tool_result":
                return False
        return True
    return False


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
                parts.append(c["text"])
        return "\n".join(parts)
    return ""


def _summarize_tool_use(c: dict) -> dict:
    name = c.get("name", "?")
    inp = c.get("input") or {}
    # Pick a representative short string from the first scalar arg.
    arg = ""
    for k, v in inp.items():
        if isinstance(v, str):
            arg = v.split("\n", 1)[0][:120]
            break
    return {"name": name, "arg": arg}


# ── aggregate (sidebar + KPIs) ────────────────────────────────────────────

def aggregate(project_dir: Path | None = None) -> dict:
    project_dir = project_dir or _project_dir()
    if not project_dir.exists():
        return {"sessions": [], "totals": {}, "project_dir": str(project_dir)}

    sessions: dict[str, dict] = {}
    tool_counts: Counter = Counter()
    model_counts: Counter = Counter()
    branch_counts: Counter = Counter()

    def sess(sid: str) -> dict:
        if sid not in sessions:
            sessions[sid] = {
                "id": sid, "title": None, "first_ts": None, "last_ts": None,
                "messages": 0, "user_messages": 0, "assistant_messages": 0,
                "tools": Counter(), "models": Counter(),
                "tokens_in": 0, "tokens_out": 0,
                "cache_read": 0, "cache_write": 0,
                "cost": 0.0, "branch": None,
            }
        return sessions[sid]

    for path in sorted(project_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid = d.get("sessionId")
                if not sid:
                    continue
                s = sess(sid)
                t = d.get("type")
                ts = _parse_ts(d.get("timestamp"))
                if ts:
                    if s["first_ts"] is None or ts < s["first_ts"]:
                        s["first_ts"] = ts
                    if s["last_ts"] is None or ts > s["last_ts"]:
                        s["last_ts"] = ts
                if d.get("gitBranch"):
                    s["branch"] = d["gitBranch"]
                    branch_counts[d["gitBranch"]] += 1

                if t == "ai-title" and d.get("aiTitle"):
                    s["title"] = d["aiTitle"]
                elif t == "user":
                    s["messages"] += 1
                    s["user_messages"] += 1
                elif t == "assistant":
                    msg = d.get("message") or {}
                    model = msg.get("model")
                    if model:
                        s["models"][model] += 1
                        model_counts[model] += 1
                    s["messages"] += 1
                    s["assistant_messages"] += 1
                    usage = msg.get("usage") or {}
                    s["tokens_in"]   += usage.get("input_tokens", 0)
                    s["tokens_out"]  += usage.get("output_tokens", 0)
                    s["cache_read"]  += usage.get("cache_read_input_tokens", 0)
                    s["cache_write"] += usage.get("cache_creation_input_tokens", 0)
                    s["cost"] += _estimate_cost(model or "", usage)
                    for c in msg.get("content") or []:
                        if isinstance(c, dict) and c.get("type") == "tool_use":
                            n = c.get("name", "?")
                            s["tools"][n] += 1
                            tool_counts[n] += 1

    sessions_out = []
    for s in sessions.values():
        primary_model = s["models"].most_common(1)[0][0] if s["models"] else None
        sessions_out.append({
            "id": s["id"],
            "title": s["title"] or "(untitled)",
            "first_ts": s["first_ts"].isoformat() if s["first_ts"] else None,
            "last_ts":  s["last_ts"].isoformat()  if s["last_ts"]  else None,
            "messages": s["messages"],
            "user_messages": s["user_messages"],
            "assistant_messages": s["assistant_messages"],
            "tool_total": sum(s["tools"].values()),
            "model": primary_model,
            "branch": s["branch"],
            "tokens_in": s["tokens_in"],
            "tokens_out": s["tokens_out"],
            "cache_read": s["cache_read"],
            "cache_write": s["cache_write"],
            "cost": round(s["cost"], 4),
        })
    sessions_out.sort(key=lambda x: x["first_ts"] or "", reverse=True)

    totals = {
        "sessions": len(sessions_out),
        "messages": sum(s["messages"] for s in sessions_out),
        "tokens_in":  sum(s["tokens_in"]  for s in sessions_out),
        "tokens_out": sum(s["tokens_out"] for s in sessions_out),
        "cache_read":  sum(s["cache_read"]  for s in sessions_out),
        "cache_write": sum(s["cache_write"] for s in sessions_out),
        "cost": round(sum(s["cost"] for s in sessions_out), 4),
        "tool_uses": sum(tool_counts.values()),
    }
    return {
        "project_dir": str(project_dir),
        "totals": totals,
        "sessions": sessions_out,
        "models":   [{"name": k, "count": v} for k, v in model_counts.most_common()],
        "tools":    [{"name": k, "count": v} for k, v in tool_counts.most_common()],
        "branches": [{"name": k, "count": v} for k, v in branch_counts.most_common()],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── turn extraction (transcript + audio anchor) ────────────────────────────

def _read_turns(jsonl_path: Path) -> list[dict]:
    """Group a session's JSONL into turns. A turn starts at each real user message."""
    turns: list[dict] = []
    current: dict | None = None
    for line in jsonl_path.open("r", encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = d.get("type")
        ts = _parse_ts(d.get("timestamp"))
        if t == "user":
            content = (d.get("message") or {}).get("content")
            if _is_real_user_content(content):
                if current:
                    turns.append(current)
                current = {
                    "user_text": _extract_text(content),
                    "user_ts": ts.isoformat() if ts else None,
                    "assistant_text": "",
                    "tools": [],
                    "anchor_ts": None,
                    "anchor_epoch": None,
                    "model": None,
                }
            else:
                # tool_result; just skip (the assistant turn that follows will use the result)
                pass
        elif t == "assistant":
            if current is None:
                # Assistant before any user message — start an orphan turn so we don't drop content
                current = {
                    "user_text": "", "user_ts": None,
                    "assistant_text": "", "tools": [], "anchor_ts": None,
                    "anchor_epoch": None, "model": None,
                }
            msg = d.get("message") or {}
            if msg.get("model"):
                current["model"] = msg["model"]
            had_text = False
            for c in msg.get("content") or []:
                if not isinstance(c, dict):
                    continue
                ct = c.get("type")
                if ct == "text" and c.get("text"):
                    if current["assistant_text"]:
                        current["assistant_text"] += "\n"
                    current["assistant_text"] += c["text"]
                    had_text = True
                elif ct == "tool_use":
                    current["tools"].append(_summarize_tool_use(c))
            if had_text and ts:
                # Anchor for audio match = timestamp of the assistant message that produced visible text.
                current["anchor_ts"] = ts.isoformat()
                current["anchor_epoch"] = ts.timestamp()
    if current:
        turns.append(current)
    return turns


# ── audio matching ────────────────────────────────────────────────────────

def _build_audio_matches(project_dir: Path, voice_dir: Path | None) -> dict[str, dict[int, str]]:
    """Global match: each audio file claimed by at most one turn.

    Returns: {session_id: {turn_index: audio_filename}}
    """
    by_session: dict[str, dict[int, str]] = defaultdict(dict)
    if not voice_dir or not voice_dir.exists():
        return by_session

    audio: list[tuple[float, str]] = []
    for p in voice_dir.iterdir():
        if not p.is_file() or p.suffix.lower() != ".mp3":
            continue
        epoch = _parse_audio_name(p.name)
        if epoch is not None:
            audio.append((epoch, p.name))
    audio.sort()

    # Collect all voice-eligible turn anchors across sessions
    anchors: list[tuple[float, str, int]] = []  # (anchor_epoch, sid, turn_idx)
    for path in sorted(project_dir.glob("*.jsonl")):
        sid = path.stem
        try:
            turns = _read_turns(path)
        except OSError:
            continue
        for i, t in enumerate(turns):
            if t["anchor_epoch"] and t["assistant_text"]:
                anchors.append((t["anchor_epoch"], sid, i))
    anchors.sort()

    ai = 0  # audio pointer (next unclaimed)
    for anchor_epoch, sid, ti in anchors:
        # Advance past audio files that fall before this anchor's window — they're orphans now.
        while ai < len(audio) and audio[ai][0] < anchor_epoch:
            ai += 1
        if ai >= len(audio):
            break
        if audio[ai][0] - anchor_epoch <= AUDIO_MATCH_WINDOW_S:
            by_session[sid][ti] = audio[ai][1]
            ai += 1
    return dict(by_session)


def _matches_cached(project_dir: Path, voice_dir: Path | None) -> dict[str, dict[int, str]]:
    now = time.monotonic()
    if (_MATCH_CACHE["by_session"] is not None
        and now - _MATCH_CACHE["at"] < _MATCH_TTL_S
        and _MATCH_CACHE["voice_dir"] == voice_dir
        and _MATCH_CACHE["project_dir"] == project_dir):
        return _MATCH_CACHE["by_session"]
    matches = _build_audio_matches(project_dir, voice_dir)
    _MATCH_CACHE.update({
        "at": now, "by_session": matches,
        "voice_dir": voice_dir, "project_dir": project_dir,
    })
    return matches


# ── public transcript API ─────────────────────────────────────────────────

def session_transcript(sid: str, project_dir: Path | None = None,
                       voice_dir: Path | None = None) -> dict:
    project_dir = project_dir or _project_dir()
    path = project_dir / f"{sid}.jsonl"
    if not path.exists():
        return {"error": "session not found", "id": sid}
    turns = _read_turns(path)
    matches = _matches_cached(project_dir, voice_dir).get(sid, {})
    out_turns = []
    for i, t in enumerate(turns):
        audio = matches.get(i)
        out_turns.append({
            "user_text": t["user_text"],
            "user_ts":   t["user_ts"],
            "assistant_text": t["assistant_text"],
            "anchor_ts": t["anchor_ts"],
            "model": t["model"],
            "tools": t["tools"],
            "audio": audio,
        })
    return {"id": sid, "turns": out_turns}


# ── HTML ──────────────────────────────────────────────────────────────────

_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Monika · sessions</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { font: 14px/1.45 -apple-system, system-ui, sans-serif; background: #0f1115; color: #e6e6e6; margin: 0; height: 100vh; display: flex; flex-direction: column; }
  header { padding: 14px 20px; border-bottom: 1px solid #232733; display: flex; gap: 18px; align-items: baseline; flex-wrap: wrap; }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; }
  header .meta { color: #8a8f98; font-size: 12px; }
  header .kpi { color: #c9ced9; font-size: 12px; }
  header .kpi b { color: #fff; font-weight: 600; }
  main { flex: 1; display: grid; grid-template-columns: 320px 1fr; min-height: 0; }
  aside { border-right: 1px solid #232733; overflow-y: auto; }
  .sess { padding: 10px 14px; border-bottom: 1px solid #1c1f27; cursor: pointer; }
  .sess:hover { background: #181b22; }
  .sess.active { background: #1f2330; border-left: 3px solid #7aa2f7; padding-left: 11px; }
  .sess .t { font-size: 13px; color: #e6e6e6; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sess .m { font-size: 11px; color: #8a8f98; margin-top: 2px; display: flex; gap: 8px; flex-wrap: wrap; }
  .sess .pill { font-size: 10px; padding: 1px 6px; border-radius: 8px; background: #232733; color: #c9ced9; }
  section { overflow-y: auto; padding: 18px 28px; }
  .turn { margin-bottom: 24px; }
  .role { font-size: 11px; color: #8a8f98; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; display: flex; gap: 8px; align-items: center; }
  .bubble { background: #181b22; border: 1px solid #232733; border-radius: 8px; padding: 10px 14px; white-space: pre-wrap; word-wrap: break-word; }
  .bubble.user { background: #1d2233; border-color: #2a3147; }
  .tools { margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap; }
  .tool { font-size: 11px; padding: 2px 8px; border-radius: 10px; background: #232733; color: #c9ced9; font-family: ui-monospace, monospace; }
  .tool .arg { color: #8a8f98; margin-left: 6px; }
  .play { background: #2a3147; color: #c9ced9; border: 1px solid #3a4360; border-radius: 6px; padding: 3px 10px; font-size: 11px; cursor: pointer; }
  .play:hover { background: #34405e; }
  audio { display: block; margin-top: 8px; width: 100%; max-width: 420px; }
  .empty { color: #8a8f98; padding: 40px; text-align: center; }
  .muted { color: #8a8f98; }
</style>
</head>
<body>
<header>
  <h1>Monika · sessions</h1>
  <span class="meta" id="meta"></span>
  <span class="kpi" id="kpi"></span>
</header>
<main>
  <aside id="list"></aside>
  <section id="view"><div class="empty">Select a session →</div></section>
</main>
<script>
const fmt = n => n == null ? "—" : Number(n).toLocaleString();
const fmt$ = n => n == null ? "—" : "$" + Number(n).toFixed(n < 1 ? 4 : 2);
const fmtDate = s => s ? new Date(s).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }) : "—";
const esc = s => (s || "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

let activeId = null;

fetch("/dashboard/data").then(r => r.json()).then(data => {
  const t = data.totals;
  document.getElementById("meta").textContent = data.project_dir;
  document.getElementById("kpi").innerHTML =
    `<b>${fmt(t.sessions)}</b> sessions · <b>${fmt(t.messages)}</b> msgs · ` +
    `<b>${fmt(t.tokens_in + t.tokens_out)}</b> tokens · <b>${fmt$(t.cost)}</b> est.`;
  const list = document.getElementById("list");
  list.innerHTML = data.sessions.map(s => `
    <div class="sess" data-id="${s.id}">
      <div class="t">${esc(s.title)}</div>
      <div class="m">
        <span>${fmtDate(s.first_ts)}</span>
        <span class="pill">${esc(s.model || "—")}</span>
        <span>${fmt(s.messages)} msgs</span>
        <span>${fmt$(s.cost)}</span>
      </div>
    </div>
  `).join("");
  list.querySelectorAll(".sess").forEach(el => {
    el.addEventListener("click", () => loadSession(el.dataset.id));
  });
  if (data.sessions.length) loadSession(data.sessions[0].id);
});

function loadSession(id) {
  activeId = id;
  document.querySelectorAll(".sess").forEach(el => el.classList.toggle("active", el.dataset.id === id));
  document.getElementById("view").innerHTML = '<div class="empty">Loading…</div>';
  fetch(`/dashboard/session/${id}`).then(r => r.json()).then(s => {
    if (s.error) {
      document.getElementById("view").innerHTML = `<div class="empty">${esc(s.error)}</div>`;
      return;
    }
    document.getElementById("view").innerHTML = s.turns.map((t, i) => renderTurn(t, i)).join("") ||
      '<div class="empty">No content.</div>';
    document.querySelectorAll(".play").forEach(btn => {
      btn.addEventListener("click", e => {
        const fn = btn.dataset.audio;
        const holder = btn.parentElement;
        let a = holder.querySelector("audio");
        if (a) { a.remove(); btn.textContent = "▶ Play"; return; }
        a = document.createElement("audio");
        a.controls = true; a.autoplay = true;
        a.src = `/dashboard/audio/${encodeURIComponent(fn)}`;
        holder.appendChild(a);
        btn.textContent = "◼ Hide";
      });
    });
  });
}

function renderTurn(t, i) {
  const userHTML = t.user_text ? `
    <div class="turn">
      <div class="role">User <span class="muted">· ${fmtDate(t.user_ts)}</span></div>
      <div class="bubble user">${esc(t.user_text)}</div>
    </div>` : "";
  const toolsHTML = t.tools.length ? `
    <div class="tools">${t.tools.map(x =>
      `<span class="tool">${esc(x.name)}${x.arg ? `<span class="arg">${esc(x.arg)}</span>` : ""}</span>`
    ).join("")}</div>` : "";
  const audioBtn = t.audio ? `
    <button class="play" data-audio="${esc(t.audio)}">▶ Play voiceline</button>` : "";
  const asstHTML = (t.assistant_text || t.tools.length) ? `
    <div class="turn">
      <div class="role">Assistant ${t.model ? `<span class="muted">· ${esc(t.model)}</span>` : ""} ${audioBtn}</div>
      ${t.assistant_text ? `<div class="bubble">${esc(t.assistant_text)}</div>` : ""}
      ${toolsHTML}
    </div>` : "";
  return userHTML + asstHTML;
}
</script>
</body>
</html>
"""


# ── routes ────────────────────────────────────────────────────────────────

_VALID_AUDIO_NAME = re.compile(r"^[\w\-. ]+\.mp3$")


def register(app: FastAPI, voice_directory: str | None = None) -> None:
    voice_dir = Path(voice_directory).resolve() if voice_directory else None

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_page():
        return HTMLResponse(_HTML)

    @app.get("/dashboard/data")
    async def dashboard_data():
        return JSONResponse(aggregate())

    @app.get("/dashboard/session/{sid}")
    async def dashboard_session(sid: str):
        if not re.fullmatch(r"[A-Za-z0-9\-]+", sid):
            raise HTTPException(400, "bad session id")
        return JSONResponse(session_transcript(sid, voice_dir=voice_dir))

    @app.get("/dashboard/audio/{filename}")
    async def dashboard_audio(filename: str):
        if not voice_dir:
            raise HTTPException(404, "voice directory not configured")
        if not _VALID_AUDIO_NAME.fullmatch(filename) or "/" in filename or ".." in filename:
            raise HTTPException(400, "bad filename")
        path = (voice_dir / filename).resolve()
        if not str(path).startswith(str(voice_dir) + os.sep):
            raise HTTPException(400, "outside voice directory")
        if not path.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(path, media_type="audio/mpeg")
