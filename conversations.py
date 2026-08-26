"""Durable conversation log.

Monika's recall of past conversations rests on this file. Every exchange the
controller completes is appended here as one JSON line, in a directory that
lives on the NFS home mount so it survives service restarts, redeploys and the
`claude` CLI's own 30-day transcript cleanup.

The log is deliberately dumb: one line per exchange, one file per day, plain
JSON. The `recall` skill greps it; nothing else needs to understand it.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_DIR = Path.home() / ".monika" / "conversations"


def log_dir() -> Path:
    override = os.getenv("MONIKA_CONVERSATIONS_DIR")
    return Path(override) if override else DEFAULT_DIR


def _path_for(when: datetime) -> Path:
    return log_dir() / f"{when:%Y-%m-%d}.jsonl"


def append(user: str, assistant: str, session: str | None = None,
           when: datetime | None = None, title: str | None = None) -> None:
    """Append one exchange. Never raises — a failed write must not break a reply."""
    when = when or datetime.now()
    entry = {
        "ts": when.strftime("%Y-%m-%dT%H:%M:%S"),
        "session": session,
        "user": (user or "").strip(),
        "assistant": (assistant or "").strip(),
    }
    if title:
        entry["title"] = title
    if not entry["user"] and not entry["assistant"]:
        return
    try:
        path = _path_for(when)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_all(since: datetime | None = None):
    """Yield entries oldest-first, optionally only those on/after `since`."""
    directory = log_dir()
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.jsonl")):
        if since and path.stem < f"{since:%Y-%m-%d}":
            continue
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and entry.get("ts", "") < since.strftime("%Y-%m-%dT%H:%M:%S"):
                continue
            yield entry


def recent(limit: int = 5, within_days: int | None = None) -> list[dict]:
    """Return the last `limit` exchanges, newest last."""
    since = datetime.now() - timedelta(days=within_days) if within_days else None
    entries = list(read_all(since=since))
    return entries[-limit:] if limit else entries
