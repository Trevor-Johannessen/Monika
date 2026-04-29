import os
import requests
from agentModel import AgentModel, function_tool

API_KEY = os.getenv("STEAM_API_KEY")
STEAM_ID = os.getenv("STEAM_ID")

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


class SteamAgent(AgentModel):
    def __init__(self, settings={}):
        super().__init__(
            name="steam_agent",
            instructions=(
                "You answer questions about the user's Steam activity and Team Fortress 2. "
                "Use getTF2FriendsOnline to list friends currently playing TF2. "
                "Use getPowerhousePlayerCount to get the total number of players on cp_powerhouse servers. "
                "Answer in plaintext without Markdown. Be brief. If no friends are playing TF2, say so directly."
            ),
            tools=[getTF2FriendsOnline, getPowerhousePlayerCount],
            settings=settings,
        )


@function_tool
def getTF2FriendsOnline() -> dict:
    """Gets the list of the user's Steam friends who are currently playing Team Fortress 2.

    Returns:
        A dict with a 'friends' list containing each friend's persona name and status.
    """
    if not API_KEY or not STEAM_ID:
        return {"error": "STEAM_API_KEY or STEAM_ID not configured in .env."}

    friends_resp = requests.get(
        "https://api.steampowered.com/ISteamUser/GetFriendList/v1/",
        params={"key": API_KEY, "steamid": STEAM_ID, "relationship": "friend"},
    )
    if friends_resp.status_code != 200:
        return {"error": f"Failed to get friend list (status {friends_resp.status_code}). The user's profile may be private."}

    friend_ids = [f["steamid"] for f in friends_resp.json().get("friendslist", {}).get("friends", [])]
    if not friend_ids:
        return {"friends": []}

    playing = []
    for i in range(0, len(friend_ids), 100):
        batch = friend_ids[i:i + 100]
        summaries = requests.get(
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": API_KEY, "steamids": ",".join(batch)},
        )
        if summaries.status_code != 200:
            continue
        for player in summaries.json().get("response", {}).get("players", []):
            if player.get("gameid") == TF2_APPID:
                playing.append({
                    "name": player.get("personaname"),
                    "status": PERSONA_STATE.get(player.get("personastate", 0), "unknown"),
                })

    return {"friends": playing}


@function_tool
def getPowerhousePlayerCount() -> dict:
    """Gets the total number of players currently on Team Fortress 2 servers running the Powerhouse (cp_powerhouse) map.

    Returns:
        A dict with 'player_count' and 'server_count'.
    """
    if not API_KEY:
        return {"error": "STEAM_API_KEY not configured in .env."}

    resp = requests.get(
        "https://api.steampowered.com/IGameServersService/GetServerList/v1/",
        params={
            "key": API_KEY,
            "filter": f"\\appid\\{TF2_APPID}\\map\\{POWERHOUSE_MAP}",
            "limit": 500,
        },
    )
    if resp.status_code != 200:
        return {"error": f"Failed to query Steam server list (status {resp.status_code})."}

    servers = resp.json().get("response", {}).get("servers", [])
    total_players = sum(s.get("players", 0) for s in servers)
    return {"player_count": total_players, "server_count": len(servers)}
