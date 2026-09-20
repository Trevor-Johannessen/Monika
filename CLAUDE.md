# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Monika

Monika is a personal AI home assistant backed by Claude via the **Claude Agent SDK** (`claude-agent-sdk`). It exposes a FastAPI server that accepts prompts (text or audio-return) and routes them through an orchestration agent that delegates to specialized sub-agents (memory, weather, Steam, etc.). It supports TTS output via OpenAI or ElevenLabs.

The SDK shells out to the `claude` CLI binary — that must be on `PATH` at runtime. The dev entrypoint inherits the user's shell PATH; the production `start` script prepends `~/.local/bin` so a per-user `claude` install works under systemd.

## Running

```bash
# Development (port 3337)
make debug

# Production install + systemd services (HTTP 3333, HTTPS 3334)
make install
```

The app is a uvicorn/FastAPI server (`server.py`). The production entrypoint is the `monika` shell script, managed by `monika.service` (systemd).

Both `make debug` and `make install` use one shared virtualenv at `/mnt/fs1/shared/venvs/monika` (on the fs1 NFS mount, so every machine reuses it) rather than a per-checkout or per-host `./venv`. `make install` creates it if missing and installs `requirements.txt` into it; the `start` script and the `monika` CLI invoke its interpreter by absolute path.

## Configuration

- `defaults.json` — default settings (checked in, values are non-sensitive placeholders)
- `settings.json` — local overrides (contains secrets like voice IDs; values are nulled before committing via `make commit`)
- `~/.credentials/` — API keys and secrets, one file per service. `credentials.py` exposes two explicit readers — `read_key(filename)` for plain-text files and `read_json(filename)` for JSON — and each consumer loads exactly the secret it needs at its point of use (there is no global env population). Both return `None`/`{}` for a missing or malformed file so callers can surface a friendly error. Plain-text files: `openai.key`, `accuweather.key`, `elevenlabs.key`. JSON files: `spotify.json` (`SPOTIFY_CLIENT_ID`/`SECRET`/`REDIRECT_URI`), `icloud.json` (`ICLOUD_APPLE_ID`/`ICLOUD_APP_PASSWORD`). Override the directory with `MONIKA_CREDENTIALS_DIR`. `accuweather.key` and `steam.json` are read by no Monika module — they belong to the `weather` and `steam` skills, whose helper scripts load them directly (honouring the same `MONIKA_CREDENTIALS_DIR` override) so those secrets never enter the agent's context. Keys are passed straight into their client constructors (`OpenAI(api_key=...)`, `ElevenLabs(api_key=...)`, etc.). The Claude Agent SDK's `claude` CLI subprocess is deliberately left to authenticate via the machine's `claude login` subscription session rather than an `ANTHROPIC_API_KEY` env var — that var takes precedence over the subscription login and would silently switch billing to pay-per-token API usage. `anthropic.key` in `~/.credentials/` is no longer read by anything here.
- `.env` — non-secret settings still loaded via `python-dotenv` (e.g. `MONIKA_DEFAULT_CALENDAR`, `MONIKA_TIMEZONE`).

Settings are merged at startup: `{**defaults, **settings}`. Key settings: `default_model`, `voice_provider` (`elevenlabs` | openai), `voice_name`, `voice_speed`, `verbose`, `webhooks`, `inital_prompt`.

## Architecture

**Client attributes:** callers may pass an `attributes` dict on the prompt body; `Controller._build_prompt_text` appends it to the user prompt as context and the model decides what to do with it. There is no per-attribute handling in the controller. `"led": true` is the convention for "the room's LED strip is available this request" — the orchestrator's system prompt explains it and the `led-strip` skill does the driving.

**Request flow:** HTTP POST `/prompt` → `server.py` → `Controller.prompt()` → `claude_agent_sdk.query()` with the orchestrator's `ClaudeAgentOptions`. Short-term conversation continuity is provided by the SDK's session resumption: the controller stores `session_id` from each `ResultMessage` and passes it back via `resume=...` on the next request. After 15 minutes of inactivity the session is dropped. The `session_id` is also mirrored to `~/.monika/state.json`, so a restart or redeploy mid-conversation picks the same session back up (subject to the same 15-minute window) instead of dropping the thread.

**Conversation memory:** Monika has two tiers of memory, and they are separate mechanisms.

*Short-term* is the SDK session above — the live thread, dropped after 15 minutes.

*Long-term* is a durable log written by `conversations.py`: one JSON line per exchange (`{ts, session, title, user, assistant}`), one file per day, under `~/.monika/conversations/` (override with `MONIKA_CONVERSATIONS_DIR`). `Controller.prompt()` appends to it after every reply, recording the **raw** user prompt rather than the context-padded text the model saw. Writes never raise — a failed log write must not break a response.

It lives in the home directory on purpose. Home is the same NFS mount on the production machine and the dev box, so the log survives redeploys, is readable from either machine, and is not tied to `/etc/monika` on deploy1's local disk.

The agent reads this log through the **`recall` skill** (`~/.claude/skills/recall/`), whose stdlib-only `recall.py` offers `search <terms>`, `recent`, `on <date>` and `days`. The orchestrator's system prompt tells it that it *does* remember past conversations and to search before claiming otherwise. Nothing is injected into the prompt automatically — recall costs a tool call only when the conversation actually reaches backwards.

Do not confuse this log with the `claude` CLI's own session transcripts in `~/.claude/projects/-usr-local-bin-monika/*.jsonl`. Those are the SDK's internal record: full of tool calls, skill attachments and sidechains, and **deleted after `cleanupPeriodDays` (30 by default)**. They were the bootstrap source, not the store — `tools/import_transcripts.py` parsed them once to backfill 253 exchanges going back to 2026-07-24. It is idempotent (deduped on session + timestamp) and safe to re-run, and defaults to the production project directory only: the dev checkout's project directory is shared with ordinary Claude Code sessions working on this repo, which are not Monika's conversations.

**Core files:**
- `orchestrationAgent.py` — Builds the orchestrator's `ClaudeAgentOptions` (system prompt + MCP servers + allowed tools). Exposes `clear_context` as an in-process MCP tool — now the only one. The orchestrator works from the SDK's built-in `Bash`, `WebSearch`, `Task` and `Skill` tools; there are no delegation sub-agents left.
- `controller.py` — Holds `session_id`, the 15-minute inactivity clock, a parallel display-history list for webhooks, and wraps each `query()` call. Builds the orchestrator options once at startup. Persists the session to `~/.monika/state.json` and appends every exchange to the durable conversation log.
- `conversations.py` — The durable conversation log: `append()`, `read_all()`, `recent()`. Deliberately dumb — plain JSON lines that the `recall` skill greps.

**Sub-agents (modules/):** *none are active.* The pattern was: each module owned one MCP server plus a "delegation tool" whose handler ran a nested `query()` with its own system prompt and `tools=[]`. Weather, Steam and calendar have all become skills, and `claudeCode.py` was replaced by the native `Task` tool. What survives in `modules/` is dormant:
- `memoryAgent.py` — ChromaDB vector store for long-term memory (OpenAI embeddings, persisted at `/var/lib/monika/memory.d`). Tags stored in `/etc/monika/tags.json`. *(disabled)*
- `scheduleTask.py` / `minecraft.py` — disabled but kept for parity.

The `agents` MCP server is gone entirely; `control` (holding `clear_context`) is the only one left. Prefer a skill over a new sub-agent unless something genuinely needs a nested agent loop — a skill costs no extra model round-trip and keeps credentials out of the model's context.

**Skills (`~/.claude/skills/<name>/SKILL.md`):** Claude Code skills, discovered by the `claude` CLI that the SDK shells out to (no longer loaded by Monika itself — the old `load_skill` MCP tool and in-repo `skills/` dir were removed). The orchestrator opts in with `skills="all"` in `build_orchestrator_options`; that one option enables the `Skill` tool and points the CLI at the skills directory. Each skill is a directory containing a `SKILL.md` with `name`/`description` frontmatter. They define behaviors like recipe management and conversation `recall`, and they are where Monika's integrations now live — `weather/`, `steam/` and `calendar/` each wrap an API in a helper script (see below). Add a new skill by creating `~/.claude/skills/<name>/SKILL.md` (see the `create-skill` skill).

**Weather:** handled by the `weather` skill (`~/.claude/skills/weather/`), not a sub-agent. Its `accuweather.py` helper reads `~/.credentials/accuweather.key` itself, resolves a place name to an AccuWeather location key, and prints a compact plain-text digest of current conditions, the 12-hour hourly forecast, or the 5-day daily forecast. The orchestrator only ever runs the script, so the API key stays out of the model's context. The script is stdlib-only Python and takes `current` / `hourly` / `daily` / `search` plus an optional `--metric`. Nothing is cached, so each question costs two API calls (location lookup + forecast) against the free tier's 50/day.

**Steam:** handled by the `steam` skill (`~/.claude/skills/steam/`), not a sub-agent. Its `steam.py` helper reads `~/.credentials/steam.json` itself and prints a plain-text digest: `friends` (friends currently in TF2, or `--all-games` for any game) and `servers [<map>]` (player and server counts for a TF2 map, default `cp_powerhouse`). Stdlib-only Python; the orchestrator only ever runs the script, so the key stays out of the model's context.

**Calendar:** handled by the `calendar` skill (`~/.claude/skills/calendar/`), not a sub-agent. Its `icloud_calendar.py` helper reads `~/.credentials/icloud.json` itself and talks CalDAV to `https://caldav.icloud.com`, printing a plain-text digest: `now`, `calendars`, `events <start> <end> [--calendar]`, `freebusy <start> <end>`, and `create --summary --start --end [--all-day ...]`. It reads (and expands recurring events) and creates, but cannot edit or delete. Two things to know: it needs `caldav`/`icalendar`, which are only in Monika's venv, so the script re-execs itself under the shared venv at `/mnt/fs1/shared/venvs/monika/bin/python` (override with `MONIKA_PYTHON`); and it is deliberately **not** named `calendar.py`, because a script by that name shadows the stdlib `calendar` module that caldav imports. `MONIKA_TIMEZONE` and `MONIKA_DEFAULT_CALENDAR` are read from the environment, falling back to parsing Monika's `.env` directly.

**Skill tone:** Monika is a conversational AI — output is often spoken aloud via TTS. When writing or editing skills, instruct the agent to respond in a natural, conversational tone. Avoid output formats that read poorly aloud (markdown tables, bulleted lists, headings, code blocks, parenthetical citations stacked together) unless the user explicitly asks for that format. Prefer flowing prose, short sentences, and natural connectives over structured layouts.

**Voice:** Two interchangeable TTS backends (`voice.py` for OpenAI, `voice_elevenlabs.py` for ElevenLabs), selected by `voice_provider` setting. Both save audio history to `voice_directory` via a forked child process.

## Adding a new sub-agent

1. Create a module in `modules/` that:
   - Defines tools with `@tool("name", "description", {"arg": type})` from `claude_agent_sdk`. Use a full JSON Schema dict in place of the type-dict when you need enums or nested objects.
   - Wraps the tools in an MCP server via `create_sdk_mcp_server(name=..., tools=[...])`.
   - Exports a `build_<name>_agent(model: str)` factory that returns a `@tool`-decorated delegation function. The handler runs `query()` internally with the sub-agent's `system_prompt`, that MCP server, `allowed_tools=["mcp__<server>__<tool>", ...]`, and `tools=[]` to strip built-ins.
2. Register the factory in `orchestrationAgent.build_orchestrator_options` (add it to the `agents_server` tools list and to the orchestrator's `allowed_tools`).

## Key patterns

- Tools are async functions decorated with `@tool` from `claude_agent_sdk`. They must return `{"content": [{"type": "text", "text": ...}], ...}` dicts; set `"is_error": True` to surface failures without breaking the agent loop.
- The orchestrator uses the SDK's built-in `Bash`, `WebSearch`, `Task` and `Skill`. MCP tool naming is `mcp__<server_name>__<tool_name>`.
- **Sub-agents on demand:** `Task` (alias `Agent`) is the SDK's native subagent tool — the orchestrator can spawn arbitrary subagents with it, including ones that run Bash. This replaced the old `claudeCode.py` module, which shelled out to `subprocess.Popen(["claude", "-p", "--dangerously-skip-permissions", ...])` and threw the output away. Named subagent types can additionally be declared via `ClaudeAgentOptions.agents={"name": AgentDefinition(...)}`, whose fields include `tools`, `model`, `permissionMode`, `maxTurns` and `background`; `background=True` returns control to the caller immediately and the job outlives the parent process. None are declared right now — subagents are spawned ad hoc.
- `clear_context` is an MCP tool with a closure over the `Controller`. Calling it nulls the controller's `session_id`, which starts a fresh SDK session on the next prompt.
- `permission_mode="bypassPermissions"` is set everywhere — this is a headless server with no human approval loop.
- The `make commit` target nulls sensitive values in `settings.json` before committing, then restores the file.
