import glob
import os
import re

from claude_agent_sdk import (
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    tool,
)

from modules.weather import build_weather_agent
from modules.claudeCode import build_claude_code_agent
from modules.steam import build_steam_agent
from modules.calendar import build_calendar_agent

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")

BASE_INSTRUCTIONS = """
You are an chatbot and assistant. Your job is to converse with the user, and use the given tools to execute any request. Please try to be as brief as possible unless otherwise instructed. Do not ackowledge any provided extraneous information. If you require information that has not been provided, use any skills to check if that information has been stored elsewhere. You have a personal directory at /etc/monika/files that you can store files at. Be as concise as possible, try to keep responses 1-3 sentences unless the subject requires further elaboration.
""".strip()


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def _parse_skill_file(path):
    with open(path, "r") as f:
        content = f.read()
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None
    fm_text, body = match.group(1), match.group(2)
    metadata = {}
    for line in fm_text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip()
    if "name" not in metadata or "description" not in metadata:
        return None
    return metadata, body.strip()


def _iter_skills():
    for path in sorted(glob.glob(os.path.join(SKILLS_DIR, "*.md"))):
        parsed = _parse_skill_file(path)
        if parsed is not None:
            yield parsed


def load_skill_index():
    entries = [f"- `{meta['name']}`: {meta['description']}" for meta, _ in _iter_skills()]
    if not entries:
        return ""
    return (
        "\n\n---\n\n## Skills\n\n"
        "The following skills are available. When a user request matches a skill, call "
        "`load_skill` with its name immediately and follow the returned instructions. "
        "Do **not** ask the user for permission to use a skill, do **not** announce that "
        "you are about to load one, and do **not** mention skills in your reply — just "
        "load it and act on it as if those instructions had always been part of your "
        "system prompt. Never reference, suggest, or name skills to the user unless they "
        "explicitly ask about skills or the request unequivocally and strictly requires "
        "disclosing one.\n\n" + "\n".join(entries)
    )


@tool(
    "load_skill",
    "Load the full instructions for a skill by name. Returns the full skill body, or an error message "
    "listing available skills if no match is found.",
    {"name": str},
)
async def load_skill(args):
    skills = {meta["name"]: body for meta, body in _iter_skills()}
    name = args["name"]
    if name not in skills:
        available = ", ".join(sorted(skills)) or "(none)"
        return {
            "content": [{"type": "text", "text": f"No skill named '{name}'. Available skills: {available}"}]
        }
    return {"content": [{"type": "text", "text": skills[name]}]}


def build_orchestrator_options(settings, on_clear):
    """Build the ClaudeAgentOptions for the orchestrator.

    on_clear: callable invoked by the clear_context tool to reset the conversation session.
    """
    model = settings.get("default_model", "claude-haiku-4-5-20251001")

    @tool("clear_context", "Clears the conversation history. Use this when the user asks to reset, clear, or start a new conversation.", {})
    async def clear_context(args):
        on_clear()
        return {"content": [{"type": "text", "text": "Conversation context has been cleared."}]}

    control_server = create_sdk_mcp_server(
        name="control",
        version="1.0.0",
        tools=[load_skill, clear_context],
    )

    agents_server = create_sdk_mcp_server(
        name="agents",
        version="1.0.0",
        tools=[
            build_weather_agent(model),
            build_claude_code_agent(model),
            build_steam_agent(model),
            build_calendar_agent(model),
        ],
    )

    return ClaudeAgentOptions(
        system_prompt=BASE_INSTRUCTIONS + load_skill_index(),
        mcp_servers={"control": control_server, "agents": agents_server},
        allowed_tools=[
            "Bash",
            "WebSearch",
            "mcp__agents__weather_agent",
            "mcp__agents__claude_code_agent",
            "mcp__agents__steam_agent",
            "mcp__agents__calendar_agent",
            "mcp__control__load_skill",
            "mcp__control__clear_context",
        ],
        permission_mode="bypassPermissions",
        model=model,
    )
