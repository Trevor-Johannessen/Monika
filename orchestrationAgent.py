from claude_agent_sdk import (
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    tool,
)

from modules.weather import build_weather_agent
from modules.claudeCode import build_claude_code_agent
from modules.steam import build_steam_agent
from modules.calendar import build_calendar_agent

BASE_INSTRUCTIONS = """
You are an chatbot and assistant. Your job is to converse with the user, and use the given tools to execute any request. Please try to be as brief as possible unless otherwise instructed. Do not ackowledge any provided extraneous information. If you require information that has not been provided, use any skills to check if that information has been stored elsewhere. You have a personal directory at /etc/monika/files that you can store files at. Be as concise as possible, try to keep responses 1-3 sentences unless the subject requires further elaboration.
""".strip()


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
        tools=[clear_context],
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
        system_prompt=BASE_INSTRUCTIONS,
        mcp_servers={"control": control_server, "agents": agents_server},
        allowed_tools=[
            "Bash",
            "WebSearch",
            "mcp__agents__weather_agent",
            "mcp__agents__claude_code_agent",
            "mcp__agents__steam_agent",
            "mcp__agents__calendar_agent",
            "mcp__control__clear_context",
        ],
        permission_mode="bypassPermissions",
        model=model,
    )
