import re
from mcrcon import MCRcon
from agentModel import AgentModel, function_tool

RCON_HOST = "localhost"
RCON_PORT = 25575
RCON_PASSWORD = ""


def _rcon(command: str) -> str:
    with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as rcon:
        return rcon.command(command)


class MinecraftAgent(AgentModel):
    def __init__(self, settings={}):
        global RCON_HOST, RCON_PORT, RCON_PASSWORD
        RCON_HOST = settings.get("minecraft_rcon_host", RCON_HOST)
        RCON_PORT = settings.get("minecraft_rcon_port", RCON_PORT)
        RCON_PASSWORD = settings.get("minecraft_rcon_password", RCON_PASSWORD)
        super().__init__(
            name="minecraft_agent",
            instructions=(
                "You are a Minecraft server assistant for a home assistant chatbot. "
                "Use the provided tools to answer questions about the server. "
                "Answer only in plaintext, no Markdown or special characters. "
                "Be concise. If no players are online, say so."
            ),
            tools=[
                getOnlinePlayers,
                getPlayerPositions,
                getPlayerHealth,
                getServerTps,
            ],
            settings=settings,
        )


@function_tool
def getOnlinePlayers() -> dict:
    """Gets the list of currently online players and the total count."""
    response = _rcon("/list")
    # Response format: "There are X of a max of Y players online: name1, name2"
    match = re.search(r"(\d+) of a max of \d+ players online:(.*)", response)
    if not match:
        return {"count": 0, "players": []}
    count = int(match.group(1))
    names_raw = match.group(2).strip()
    players = [n.strip() for n in names_raw.split(",") if n.strip()]
    return {"count": count, "players": players}


@function_tool
def getPlayerPositions() -> dict:
    """Gets the current position (x, y, z) and dimension of all online players.

    Returns a dict mapping each player name to their position and dimension.
    """
    online = getOnlinePlayers()
    if online["count"] == 0:
        return {}

    result = {}
    for player in online["players"]:
        pos_resp = _rcon(f"/data get entity {player} Pos")
        dim_resp = _rcon(f"/data get entity {player} Dimension")

        # Pos response: "... has the following entity data: [Xd, Yd, Zd]"
        pos_match = re.search(r"\[([+-]?\d+\.?\d*)d?, ([+-]?\d+\.?\d*)d?, ([+-]?\d+\.?\d*)d?\]", pos_resp)
        dim_match = re.search(r'"(minecraft:[^"]+)"', dim_resp)

        result[player] = {
            "x": float(pos_match.group(1)) if pos_match else None,
            "y": float(pos_match.group(2)) if pos_match else None,
            "z": float(pos_match.group(3)) if pos_match else None,
            "dimension": dim_match.group(1) if dim_match else None,
        }
    return result


@function_tool
def getPlayerHealth() -> dict:
    """Gets the current health and food level of all online players.

    Returns a dict mapping each player name to their health (max 20) and food level (max 20).
    """
    online = getOnlinePlayers()
    if online["count"] == 0:
        return {}

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
    return result


@function_tool
def getServerTps() -> str:
    """Gets the current TPS (ticks per second) of the server. 20 TPS is ideal. Paper servers only."""
    return _rcon("/tps")
