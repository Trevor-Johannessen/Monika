import os
from datetime import datetime

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

SCHEDULE_AGENT_INSTRUCTIONS = (
    "You are apart of a larger chatbot. You handle running tasks in the future. If you are told to run "
    "something in some time relative to now, get the current time first. You MUST call a tool before "
    "answering — never respond from your own knowledge."
)


@tool("getDatetime", "Gets the current date and time.", {})
async def get_datetime(args):
    return {"content": [{"type": "text", "text": datetime.now().strftime("%Y-%m-%d %H:%M")}]}


@tool(
    "scheduleTask",
    "Schedules a task at a given date and time.",
    {"time": str, "task": str},
)
async def schedule_task(args):
    task = args["task"].replace('"', "").replace("'", "")
    try:
        rc = os.system(
            f"""echo \"curl -X POST http://localhost:3333/prompt -H \\"Content-Type: application/json\\" -d \'{{\\"return_type\\": \\"text\\", \\"prompt\\": \\"{task}\\"}}'\" | at {args['time']}"""
        )
    except Exception as e:
        return {"content": [{"type": "text", "text": str(e)}], "is_error": True}
    if rc == 0:
        return {"content": [{"type": "text", "text": "Success!"}]}
    return {"content": [{"type": "text", "text": "Could not schedule task."}], "is_error": True}


@tool("listTask", "Lists all currently queued one off tasks.", {})
async def list_task(args):
    import subprocess

    result = subprocess.run(["atq"], capture_output=True, text=True)
    return {"content": [{"type": "text", "text": result.stdout or "(no jobs queued)"}]}


@tool(
    "removeTask",
    "Removes a scheduled job by its job number.",
    {"job_number": int},
)
async def remove_task(args):
    rc = os.system(f"atrm {args['job_number']}")
    if rc == 0:
        return {"content": [{"type": "text", "text": "Success!"}]}
    return {"content": [{"type": "text", "text": "Could not remove task."}], "is_error": True}


schedule_tools_server = create_sdk_mcp_server(
    name="schedule_tools",
    version="1.0.0",
    tools=[get_datetime, schedule_task, list_task, remove_task],
)


def build_schedule_agent(model: str):
    @tool(
        "schedule_agent",
        "Routes scheduling requests (run X at time Y, list jobs, remove jobs) to a specialized agent. "
        "Pass the user's request as 'request'.",
        {"request": str},
    )
    async def schedule_agent(args):
        text = ""
        async for msg in query(
            prompt=args["request"],
            options=ClaudeAgentOptions(
                system_prompt=SCHEDULE_AGENT_INSTRUCTIONS,
                mcp_servers={"schedule_tools": schedule_tools_server},
                allowed_tools=[
                    "mcp__schedule_tools__getDatetime",
                    "mcp__schedule_tools__scheduleTask",
                    "mcp__schedule_tools__listTask",
                    "mcp__schedule_tools__removeTask",
                ],
                tools=[],
                permission_mode="bypassPermissions",
                model=model,
            ),
        ):
            if isinstance(msg, ResultMessage) and msg.subtype == "success":
                text = msg.result
        return {"content": [{"type": "text", "text": text}]}

    return schedule_agent
