import json
import requests
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

from credentials import read_json

_steam = read_json("steam.json")
API_KEY = _steam.get("api_key")
STEAM_ID = _steam.get("profile_id")

TF2_APPID = "440"
POWERHOUSE_MAP = "cp_powerhouse"

PERSONA_STATE = {
    0: "offline",
    1: "online",
    2: "busy",
    3: "away",
    4: "snooze",
    5: "looking to trade",
    6: "looking to play",
}

STEAM_AGENT_INSTRUCTIONS = (
    "You answer questions about the user's Steam activity and Team Fortress 2. "
    "Use getTF2FriendsOnline to list friends currently playing TF2. "
    "Use getPowerhousePlayerCount to get the total number of players on cp_powerhouse servers. "
    "Answer in plaintext without Markdown. Be brief. If no friends are playing TF2, say so directly."
)


@tool(
    "getTF2FriendsOnline",
    "Gets the list of the user's Steam friends who are currently playing Team Fortress 2. Returns a dict "
    "with a 'friends' list containing each friend's persona name and status.",
    {},
)
async def get_tf2_friends_online(args):
    if not API_KEY or not STEAM_ID:
        return {
            "content": [{"type": "text", "text": "api_key or profile_id not configured in ~/.credentials/steam.json."}],
            "is_error": True,
        }

    friends_resp = requests.get(
        "https://api.steampowered.com/ISteamUser/GetFriendList/v1/",
        params={"key": API_KEY, "steamid": STEAM_ID, "relationship": "friend"},
    )
    if friends_resp.status_code != 200:
        return {
            "content": [
                {"type": "text", "text": f"Failed to get friend list (status {friends_resp.status_code}). The user's profile may be private."}
            ],
            "is_error": True,
        }

    friend_ids = [f["steamid"] for f in friends_resp.json().get("friendslist", {}).get("friends", [])]
    if not friend_ids:
        return {"content": [{"type": "text", "text": json.dumps({"friends": []})}]}

    playing = []
    for i in range(0, len(friend_ids), 100):
        batch = friend_ids[i : i + 100]
        summaries = requests.get(
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": API_KEY, "steamids": ",".join(batch)},
        )
        if summaries.status_code != 200:
            continue
        for player in summaries.json().get("response", {}).get("players", []):
            if player.get("gameid") == TF2_APPID:
                playing.append(
                    {
                        "name": player.get("personaname"),
                        "status": PERSONA_STATE.get(player.get("personastate", 0), "unknown"),
                    }
                )

    return {"content": [{"type": "text", "text": json.dumps({"friends": playing})}]}


@tool(
    "getPowerhousePlayerCount",
    "Gets the total number of players currently on Team Fortress 2 servers running the Powerhouse "
    "(cp_powerhouse) map. Returns a dict with 'player_count' and 'server_count'.",
    {},
)
async def get_powerhouse_player_count(args):
    if not API_KEY:
        return {
            "content": [{"type": "text", "text": "api_key not configured in ~/.credentials/steam.json."}],
            "is_error": True,
        }

    resp = requests.get(
        "https://api.steampowered.com/IGameServersService/GetServerList/v1/",
        params={
            "key": API_KEY,
            "filter": f"\\appid\\{TF2_APPID}\\map\\{POWERHOUSE_MAP}",
            "limit": 500,
        },
    )
    if resp.status_code != 200:
        return {
            "content": [{"type": "text", "text": f"Failed to query Steam server list (status {resp.status_code})."}],
            "is_error": True,
        }

    servers = resp.json().get("response", {}).get("servers", [])
    total_players = sum(s.get("players", 0) for s in servers)
    return {
        "content": [{"type": "text", "text": json.dumps({"player_count": total_players, "server_count": len(servers)})}]
    }


steam_tools_server = create_sdk_mcp_server(
    name="steam_tools",
    version="1.0.0",
    tools=[get_tf2_friends_online, get_powerhouse_player_count],
)


def build_steam_agent(model: str):
    @tool(
        "steam_agent",
        "Routes Steam and Team Fortress 2 questions to a specialized agent. Pass the user's request as 'request'.",
        {"request": str},
    )
    async def steam_agent(args):
        text = ""
        async for msg in query(
            prompt=args["request"],
            options=ClaudeAgentOptions(
                system_prompt=STEAM_AGENT_INSTRUCTIONS,
                mcp_servers={"steam_tools": steam_tools_server},
                allowed_tools=[
                    "mcp__steam_tools__getTF2FriendsOnline",
                    "mcp__steam_tools__getPowerhousePlayerCount",
                ],
                tools=[],
                permission_mode="bypassPermissions",
                model=model,
            ),
        ):
            if isinstance(msg, ResultMessage) and msg.subtype == "success":
                text = msg.result
        return {"content": [{"type": "text", "text": text}]}

    return steam_agent
