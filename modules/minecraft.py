import json
import re

from mcrcon import MCRcon

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

RCON_HOST = "localhost"
RCON_PORT = 25575
RCON_PASSWORD = ""

MINECRAFT_AGENT_INSTRUCTIONS = (
    "You are a Minecraft server assistant for a home assistant chatbot. "
    "Use the provided tools to answer questions about the server. "
    "Answer only in plaintext, no Markdown or special characters. "
    "Be concise. If no players are online, say so."
)


def _rcon(command: str) -> str:
    with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as rcon:
        return rcon.command(command)


def _parse_online_players() -> dict:
    response = _rcon("/list")
    match = re.search(r"(\d+) of a max of \d+ players online:(.*)", response)
    if not match:
        return {"count": 0, "players": []}
    count = int(match.group(1))
    names_raw = match.group(2).strip()
    players = [n.strip() for n in names_raw.split(",") if n.strip()]
    return {"count": count, "players": players}


@tool("getOnlinePlayers", "Gets the list of currently online players and the total count.", {})
async def get_online_players(args):
    return {"content": [{"type": "text", "text": json.dumps(_parse_online_players())}]}


@tool(
    "getPlayerPositions",
    "Gets the current position (x, y, z) and dimension of all online players. Returns a dict mapping "
    "each player name to their position and dimension.",
    {},
)
async def get_player_positions(args):
    online = _parse_online_players()
    if online["count"] == 0:
        return {"content": [{"type": "text", "text": json.dumps({})}]}

    result = {}
    for player in online["players"]:
        pos_resp = _rcon(f"/data get entity {player} Pos")
        dim_resp = _rcon(f"/data get entity {player} Dimension")

        pos_match = re.search(
            r"\[([+-]?\d+\.?\d*)d?, ([+-]?\d+\.?\d*)d?, ([+-]?\d+\.?\d*)d?\]", pos_resp
        )
        dim_match = re.search(r'"(minecraft:[^"]+)"', dim_resp)

        result[player] = {
            "x": float(pos_match.group(1)) if pos_match else None,
            "y": float(pos_match.group(2)) if pos_match else None,
            "z": float(pos_match.group(3)) if pos_match else None,
            "dimension": dim_match.group(1) if dim_match else None,
        }
    return {"content": [{"type": "text", "text": json.dumps(result)}]}


@tool(
    "getPlayerHealth",
    "Gets the current health and food level of all online players. Returns a dict mapping each player "
    "name to their health (max 20) and food level (max 20).",
    {},
)
async def get_player_health(args):
    online = _parse_online_players()
    if online["count"] == 0:
        return {"content": [{"type": "text", "text": json.dumps({})}]}

    result = {}
    for player in online["players"]:
        health_resp = _rcon(f"/data get entity {player} Health")
        food_resp = _rcon(f"/data get entity {player} FoodLevel")

        health_match = re.search(r"([\d.]+)f?$", health_resp.strip())
        food_match = re.search(r"(\d+)$", food_resp.strip())

        result[player] = {
            "health": float(health_match.group(1)) if health_match else None,
            "food": int(food_match.group(1)) if food_match else None,
        }
    return {"content": [{"type": "text", "text": json.dumps(result)}]}


@tool(
    "getServerTps",
    "Gets the current TPS (ticks per second) of the server. 20 TPS is ideal. Paper servers only.",
    {},
)
async def get_server_tps(args):
    return {"content": [{"type": "text", "text": _rcon("/tps")}]}


minecraft_tools_server = create_sdk_mcp_server(
    name="minecraft_tools",
    version="1.0.0",
    tools=[get_online_players, get_player_positions, get_player_health, get_server_tps],
)


def build_minecraft_agent(model: str, settings: dict | None = None):
    global RCON_HOST, RCON_PORT, RCON_PASSWORD
    if settings:
        RCON_HOST = settings.get("minecraft_rcon_host", RCON_HOST)
        RCON_PORT = settings.get("minecraft_rcon_port", RCON_PORT)
        RCON_PASSWORD = settings.get("minecraft_rcon_password", RCON_PASSWORD)

    @tool(
        "minecraft_agent",
        "Routes Minecraft server questions (online players, positions, health, TPS) to a specialized "
        "agent. Pass the user's request as 'request'.",
        {"request": str},
    )
    async def minecraft_agent(args):
        text = ""
        async for msg in query(
            prompt=args["request"],
            options=ClaudeAgentOptions(
                system_prompt=MINECRAFT_AGENT_INSTRUCTIONS,
                mcp_servers={"minecraft_tools": minecraft_tools_server},
                allowed_tools=[
                    "mcp__minecraft_tools__getOnlinePlayers",
                    "mcp__minecraft_tools__getPlayerPositions",
                    "mcp__minecraft_tools__getPlayerHealth",
                    "mcp__minecraft_tools__getServerTps",
                ],
                tools=[],
                permission_mode="bypassPermissions",
                model=model,
            ),
        ):
            if isinstance(msg, ResultMessage) and msg.subtype == "success":
                text = msg.result
        return {"content": [{"type": "text", "text": text}]}

    return minecraft_agent
