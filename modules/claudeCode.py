import shutil
import subprocess
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

CLAUDE_PATH = shutil.which("claude") or "claude"

CLAUDE_CODE_AGENT_INSTRUCTIONS = (
    "ONLY use this tool when the user explicitly asks to run an agent, e.g. 'run an agent to...', "
    "'start an agent that...', 'launch an agent for...'. Do NOT use this tool for general coding "
    "questions or tasks that don't specifically request an agent."
)


@tool(
    "run_claude_agent",
    "Runs a Claude Code agent in the background to perform a task. The agent runs non-blocking and "
    "will complete independently.",
    {"prompt": str, "working_directory": str},
)
async def run_claude_agent(args):
    try:
        subprocess.Popen(
            [CLAUDE_PATH, "-p", "--dangerously-skip-permissions", args["prompt"]],
            cwd=args["working_directory"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return {
            "content": [
                {"type": "text", "text": f"Claude Code agent has been launched in the background with prompt: {args['prompt']}"}
            ]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Failed to launch Claude Code agent: {e}"}],
            "is_error": True,
        }


claude_code_tools_server = create_sdk_mcp_server(
    name="claude_code_tools",
    version="1.0.0",
    tools=[run_claude_agent],
)


def build_claude_code_agent(model: str):
    @tool(
        "claude_code_agent",
        "Routes 'run an agent' style requests to a specialized agent that can launch background Claude "
        "Code workers. Pass the user's request as 'request'.",
        {"request": str},
    )
    async def claude_code_agent(args):
        text = ""
        async for msg in query(
            prompt=args["request"],
            options=ClaudeAgentOptions(
                system_prompt=CLAUDE_CODE_AGENT_INSTRUCTIONS,
                mcp_servers={"claude_code_tools": claude_code_tools_server},
                allowed_tools=["mcp__claude_code_tools__run_claude_agent"],
                tools=[],
                permission_mode="bypassPermissions",
                model=model,
            ),
        ):
            if isinstance(msg, ResultMessage) and msg.subtype == "success":
                text = msg.result
        return {"content": [{"type": "text", "text": text}]}

    return claude_code_agent
