import os
import glob
import re
import subprocess
from agentModel import AgentModel, function_tool

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}
SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")

BASE_INSTRUCTIONS = """
You are an chatbot and assistant. Your job is to converse with the user, and use the given tools to execute any request. Please try to be as brief as possible unless otherwise instructed. Do not ackowledge any provided extraneous information. If you require information that has not been provided, use any skills to check if that information has been stored elsewhere. You have a personal directory at /etc/monika/files that you can store files at. Be as concise as possible, try to keep responses 1-3 sentences unless the subject requires further elaboration.
""".strip()


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def _parse_skill_file(path):
    """Return (metadata_dict, body) for a skill file, or None if no valid frontmatter."""
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
    """Return a summary listing of available skills (name + description only)."""
    entries = [f"- `{meta['name']}`: {meta['description']}" for meta, _ in _iter_skills()]
    if not entries:
        return ""
    return (
        "\n\n---\n\n## Skills\n\n"
        "The following skills are available. When a user request matches a skill, call "
        "`load_skill` with its name to retrieve the full instructions, then follow them.\n\n"
        + "\n".join(entries)
    )


@function_tool
def load_skill(name: str) -> str:
    """Load the full instructions for a skill by name.

    Args:
        name: The name of the skill, matching the identifier shown in the skill index.

    Returns:
        The full skill body, or an error message listing available skills if no match is found.
    """
    skills = {meta["name"]: body for meta, body in _iter_skills()}
    if name not in skills:
        available = ", ".join(sorted(skills)) or "(none)"
        return f"No skill named '{name}'. Available skills: {available}"
    return skills[name]


@function_tool
def bash(command: str) -> str:
    """Executes a bash command and returns the output.

    Args:
        command: The shell command to execute.

    Returns:
        The stdout and stderr output of the command.
    """
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=30
    )
    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr if output else result.stderr
    return output if output else "(no output)"


class OrchestrationAgent(AgentModel):
    def __init__(self, agents=[], outputType=None, settings={}, context=None):
        instructions = BASE_INSTRUCTIONS + load_skill_index()

        tools = [agent.as_tool(agent.name, agent.instructions) for agent in agents] + [bash, load_skill, WEB_SEARCH_TOOL]

        if context is not None:
            @function_tool
            def clear_context() -> str:
                """Clears the conversation history. Use this when the user asks to reset, clear, or start a new conversation."""
                context.clear()
                return "Conversation context has been cleared."
            tools.append(clear_context)

        super().__init__(
            name="orchestration_agent",
            instructions=instructions,
            tools=tools,
            settings=settings
        )
