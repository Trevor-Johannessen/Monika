#!/usr/bin/env python3
"""Backfill the durable conversation log from the `claude` CLI's own transcripts.

The Claude Agent SDK shells out to the `claude` CLI, which writes a JSONL
transcript per session under ~/.claude/projects/<slugified-cwd>/. Those files
already hold every conversation Monika has ever had — but the CLI deletes them
after `cleanupPeriodDays` (30 by default), and their format is full of tool
calls, skill attachments and sidechains.

This script reads them once, pulls out just the user prompt / assistant reply
pairs, and writes them into the durable log that the `recall` skill searches.
It is idempotent: exchanges already present (same session + timestamp) are
skipped, so it is safe to re-run.

    ./venv/bin/python3 tools/import_transcripts.py            # import
    ./venv/bin/python3 tools/import_transcripts.py --dry-run  # preview only
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import conversations  # noqa: E402

# The production service runs with cwd=/usr/local/bin/monika, so the CLI files
# its transcripts under that slugified name. Only prod is imported by default:
# the dev checkout's project directory is shared with ordinary Claude Code
# sessions working on this repo, and those are not Monika's conversations.
# Pass --project to pull in another directory deliberately.
DEFAULT_PROJECTS = ["-usr-local-bin-monika"]

# The controller appends context to every prompt; strip it back off so the log
# holds what the user actually said.
# Harness plumbing that reaches the model as a "user" turn but was never spoken
# by the user. Present in Claude Code sessions rather than Monika's, but cheap
# to guard against when --project pulls in another directory.
META_PREFIXES = ("<task-notification>", "<local-command-", "<command-name>",
                 "<system-reminder>", "Caveat: The messages below")

NOISE_MARKERS = (
    "\n\nBelow is information that may help with the above prompt.",
    "\n\nBelow if extra information from the user.",
    "\n\nPending reminders (evaluate each Trigger",
    "\n\nIMPORTANT: Respond using complete words only.",
)


def clean_prompt(text: str) -> str:
    for marker in NOISE_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    return text.strip()


def _text_of(content) -> str:
    """Flatten a message content field to its plain text, ignoring tool blocks."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(p for p in parts if p)


def _is_real_prompt(record: dict) -> bool:
    """True for a record that is the user actually talking, not tool plumbing."""
    if record.get("type") != "user" or record.get("isSidechain"):
        return False
    if record.get("toolUseResult") is not None or record.get("isMeta"):
        return False
    content = record.get("message", {}).get("content")
    if isinstance(content, list):
        # tool_result blocks and skill attachments arrive as user records
        if any(isinstance(b, dict) and b.get("type") != "text" for b in content):
            return False
    text = _text_of(content).strip()
    return bool(text) and not text.startswith(META_PREFIXES)


def _local(ts: str) -> datetime:
    """Transcript timestamps are UTC ISO-8601; the log is local time."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except (ValueError, AttributeError):
        return datetime.now()


def exchanges_in(path: str):
    """Yield (when, session, title, user, assistant) pairs from one transcript."""
    records = []
    title = None
    try:
        with open(path, errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") == "ai-title":
                    title = record.get("aiTitle") or title
                else:
                    records.append(record)
    except OSError:
        return

    session = Path(path).stem
    pending = None  # (when, prompt text)
    reply = []

    def flush():
        if pending and reply:
            yield_when, yield_user = pending
            return (yield_when, session, title, yield_user, "\n".join(reply).strip())
        return None

    for record in records:
        if _is_real_prompt(record):
            done = flush()
            if done:
                yield done
            pending = (_local(record.get("timestamp", "")),
                       clean_prompt(_text_of(record["message"]["content"])))
            reply = []
        elif (record.get("type") == "assistant" and not record.get("isSidechain")
              and not record.get("isApiErrorMessage") and pending):
            text = _text_of(record.get("message", {}).get("content")).strip()
            if text:
                reply.append(text)

    done = flush()
    if done:
        yield done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be imported without writing")
    parser.add_argument("--project", action="append", metavar="DIR",
                        help="project directory name under ~/.claude/projects "
                             "(repeatable; defaults to Monika's prod and dev dirs)")
    args = parser.parse_args()

    root = Path(os.getenv("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "projects"
    projects = args.project or DEFAULT_PROJECTS

    # Everything already logged, so a re-run adds nothing twice.
    seen = {(e.get("session"), e.get("ts")) for e in conversations.read_all()}

    found = imported = 0
    for name in projects:
        directory = root / name
        if not directory.is_dir():
            print(f"skipping {name} (no such project directory)")
            continue
        files = sorted(glob.glob(str(directory / "*.jsonl")))
        print(f"{name}: {len(files)} transcript(s)")
        for path in files:
            for when, session, title, user, assistant in exchanges_in(path):
                found += 1
                key = (session, when.strftime("%Y-%m-%dT%H:%M:%S"))
                if key in seen:
                    continue
                seen.add(key)
                imported += 1
                if not args.dry_run:
                    conversations.append(user, assistant, session=session,
                                         when=when, title=title)

    verb = "would import" if args.dry_run else "imported"
    print(f"\n{found} exchange(s) found, {verb} {imported} "
          f"({found - imported} already present)")
    if not args.dry_run and imported:
        print(f"written to {conversations.log_dir()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
