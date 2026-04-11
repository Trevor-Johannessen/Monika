# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Monika

Monika is a personal AI home assistant backed by Claude (Anthropic API). It exposes a FastAPI server that accepts prompts (text or audio-return) and routes them through an orchestration agent that delegates to specialized sub-agents (memory, weather, Spotify). It supports TTS output via OpenAI or ElevenLabs.

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

**Request flow:** HTTP POST `/prompt` → `server.py` → `Controller.prompt()` → `OrchestrationAgent.run()` → Claude API with tool-use loop

**Core files:**
- `agentModel.py` — Base `AgentModel` class wrapping the Anthropic API. Handles tool-use loops, the `@function_tool` decorator (auto-generates tool schemas from Google-style docstrings + type hints), and agent-as-tool delegation via `as_tool()`.
- `orchestrationAgent.py` — Top-level agent. Composes sub-agents as tools, includes a `bash` tool and web search. Loads skill prompts from `skills/*.md` into its system instructions.
- `controller.py` — Wires up all sub-agents, manages conversation `Context`, and dispatches webhooks.
- `context.py` — Conversation history with 15-minute inactivity auto-clear.

**Sub-agents (modules/):**
- `memoryAgent.py` — ChromaDB vector store for long-term memory (OpenAI embeddings, persisted at `/var/lib/monika/memory.d`). Tags stored in `/etc/monika/tags.json`.
- `weather.py` — AccuWeather API (location search → hourly/daily forecasts).
- `spotify.py` — Spotify playback control via spotipy. Uses `ModelSettings(tool_choice="required")` to force tool use on first turn.

**Skills (`skills/*.md`):** Markdown files loaded into the orchestration agent's system prompt. They define behaviors like recipe management. Add new skills by creating a `.md` file in `skills/`.

**Voice:** Two interchangeable TTS backends (`voice.py` for OpenAI, `voice_elevenlabs.py` for ElevenLabs), selected by `voice_provider` setting. Both save audio history to `voice_directory` via a forked child process.

## Adding a new sub-agent

1. Create a module in `modules/` that subclasses `AgentModel`.
2. Define tool functions with `@function_tool` (use Google-style docstrings for arg descriptions).
3. Register it in `controller.py` by appending to `agent_list`.

## Key patterns

- Tools are plain Python functions decorated with `@function_tool`. The decorator introspects type hints and docstrings to generate Anthropic tool schemas automatically.
- Sub-agents are exposed to the orchestrator as tools via `agent.as_tool(name, description)` — the orchestrator calls them by passing a `request` string.
- Server-side tools (like `web_search`) are passed as raw dicts in the tools list.
- The `make commit` target nulls sensitive values in `settings.json` before committing, then restores the file.
