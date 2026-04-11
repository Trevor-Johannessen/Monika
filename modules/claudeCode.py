import subprocess
import shutil
from agentModel import AgentModel, function_tool

CLAUDE_PATH = shutil.which("claude") or "claude"


@function_tool
def run_claude_agent(prompt: str, working_directory: str) -> str:
    """Runs a Claude Code agent in the background to perform a task. The agent runs non-blocking and will complete independently.

    Args:
        prompt: The task or prompt to give the Claude Code agent.
        working_directory: The directory the agent should work in.
    """
    try:
        subprocess.Popen(
            [CLAUDE_PATH, "-p", "--dangerously-skip-permissions", prompt],
            cwd=working_directory,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return f"Claude Code agent has been launched in the background with prompt: {prompt}"
    except Exception as e:
        return f"Failed to launch Claude Code agent: {e}"


class ClaudeCodeAgent(AgentModel):
    def __init__(self, settings={}):
        super().__init__(
            name="claude_code_agent",
            instructions="ONLY use this tool when the user explicitly asks to run an agent, e.g. 'run an agent to...', 'start an agent that...', 'launch an agent for...'. Do NOT use this tool for general coding questions or tasks that don't specifically request an agent.",
            tools=[run_claude_agent],
            settings=settings,
        )
