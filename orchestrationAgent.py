import os
import glob
import subprocess
from agentModel import AgentModel, function_tool

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}
SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")

BASE_INSTRUCTIONS = """
You are an chatbot and assistant. Your job is to converse with the user, and use the given tools to execute any request. Please try to be as brief as possible unless otherwise instructed. Do not ackowledge any provided extraneous information. If you require information that has not been provided, use any skills to check if that information has been stored elsewhere. You have a personal directory at /etc/monika/files that you can store files at. Be as concise as possible, try to keep responses 1-3 sentences unless the subject requires further elaboration.
""".strip()


def load_skills():
    """Load all markdown files from the skills directory and return as a combined string."""
    skill_files = sorted(glob.glob(os.path.join(SKILLS_DIR, "*.md")))
    sections = []
    for path in skill_files:
        with open(path, "r") as f:
            sections.append(f.read().strip())
    if not sections:
        return ""
    return "\n\n---\n\n## Skills\n\n" + "\n\n---\n\n".join(sections)


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
    def __init__(self, agents=[], outputType=None, settings={}):
        instructions = BASE_INSTRUCTIONS + load_skills()
        super().__init__(
            name="orchestration_agent",
            instructions=instructions,
            tools=[agent.as_tool(agent.name, agent.instructions) for agent in agents]
                  + [bash, WEB_SEARCH_TOOL],
            settings=settings
        )
