# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Monika

Monika is a personal AI home assistant backed by Claude via the **Claude Agent SDK** (`claude-agent-sdk`). It exposes a FastAPI server that accepts prompts (text or audio-return) and routes them through an orchestration agent that delegates to specialized sub-agents (memory, weather, Steam, etc.). It supports TTS output via OpenAI or ElevenLabs.

The SDK shells out to the `claude` CLI binary — that must be on `PATH` at runtime. The dev entrypoint inherits the user's shell PATH; the production `start` script prepends `~/.local/bin` so a per-user `claude` install works under systemd.

## Running

```bash
# Development (port 3334)
make debug

# Production install + systemd service (port 3333)
make install
```

The app is a uvicorn/FastAPI server (`server.py`). The production entrypoint is the `monika` shell script, managed by `monika.service` (systemd).

## Configuration

- `defaults.json` — default settings (checked in, values are non-sensitive placeholders)
- `settings.json` — local overrides (contains secrets like voice IDs; values are nulled before committing via `make commit`)
- `.env` — API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, ACCUWEATHER_API_KEY, SPOTIFY_CLIENT_ID, etc.)

Settings are merged at startup: `{**defaults, **settings}`. Key settings: `default_model`, `voice_provider` (`elevenlabs` | openai), `voice_name`, `voice_speed`, `verbose`, `webhooks`, `inital_prompt`.

## Architecture

**Request flow:** HTTP POST `/prompt` → `server.py` → `Controller.prompt()` → `claude_agent_sdk.query()` with the orchestrator's `ClaudeAgentOptions`. Conversation continuity is provided by the SDK's session resumption: the controller stores `session_id` from each `ResultMessage` and passes it back via `resume=...` on the next request. After 15 minutes of inactivity the session is dropped.

**Core files:**
- `orchestrationAgent.py` — Builds the orchestrator's `ClaudeAgentOptions` (system prompt + MCP servers + allowed tools). Exposes `load_skill` and `clear_context` as in-process MCP tools. The orchestrator can use the SDK's built-in `Bash` and `WebSearch` tools plus the delegation tools from each sub-agent.
- `controller.py` — Holds `session_id`, the 15-minute inactivity clock, a parallel display-history list for webhooks, and wraps each `query()` call. Builds the orchestrator options once at startup.

**Sub-agents (modules/):** each module owns one MCP server (its tools) and one "delegation tool" exposed to the orchestrator. The delegation tool's handler runs `query()` internally with that sub-agent's system prompt, MCP server, and `tools=[]` (to strip built-ins from the sub-agent's context).
- `memoryAgent.py` — ChromaDB vector store for long-term memory (OpenAI embeddings, persisted at `/var/lib/monika/memory.d`). Tags stored in `/etc/monika/tags.json`. *(currently disabled in `controller.py`)*
- `weather.py` — AccuWeather API (location search → hourly/daily forecasts).
- `steam.py` — Steam Web API (friends in TF2, server population).
- `calendar.py` — Apple iCloud calendar over CalDAV (`caldav` library). Reads/searches events and creates new ones; cannot edit or delete. Auth via `ICLOUD_APPLE_ID` + `ICLOUD_APP_PASSWORD` (an app-specific password) in `.env`; optional `MONIKA_TIMEZONE` and `MONIKA_DEFAULT_CALENDAR`.
- `claudeCode.py` — Launches background `claude` CLI workers (only when explicitly requested).
- `scheduleTask.py` / `minecraft.py` — disabled but kept for parity.

**Skills (`skills/*.md`):** Markdown files loaded into the orchestration agent's system prompt. They define behaviors like recipe management. Add new skills by creating a `.md` file in `skills/`.

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
- Sub-agents are exposed to the orchestrator as MCP tools that internally run `query()`. The naming convention is `mcp__<server_name>__<tool_name>`.
- The orchestrator uses the SDK's built-in `Bash` and `WebSearch`. Sub-agents disable built-ins via `tools=[]` so they only see their own MCP tools.
- `clear_context` is an MCP tool with a closure over the `Controller`. Calling it nulls the controller's `session_id`, which starts a fresh SDK session on the next prompt.
- `permission_mode="bypassPermissions"` is set everywhere — this is a headless server with no human approval loop.
- The `make commit` target nulls sensitive values in `settings.json` before committing, then restores the file.
