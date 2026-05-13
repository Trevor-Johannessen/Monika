import json
import os
import requests
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

api_key = os.getenv("ACCUWEATHER_API_KEY")

WEATHER_AGENT_INSTRUCTIONS = (
    "You are a meteorologist apart of a larger home assistant chatbot. Your job is to get weather about "
    "given places and give a summary of relevant information. Assume the user only wants the current weather "
    "conditions unless otherwise specified. You have tools to help get the weather via the AccuWeather API. "
    "Answer only in plaintext and do not provide any links. Do not use Markdown or any other stylings. Any "
    "sources used should not be stated. Answer in Imperial units unless otherwise specified. Default to the "
    "shortest timespan available unless otherwise specified. Ignore any information that isn't specified by "
    "the prompt except percipitation. Mention rain or snow if there is any, do not mention if there isn't. "
    "You do not need to mention the unit of temperature."
)


@tool(
    "getLocationKey",
    "Gets the location key of a given town or city by name. Returns a list of cities and additional "
    "information about them. The location key is stored in the 'Key' attribute.",
    {"location_name": str},
)
async def get_location_key(args):
    response = requests.get(
        "http://dataservice.accuweather.com/locations/v1/cities/search",
        params={"apikey": api_key, "q": args["location_name"]},
    )
    if response.status_code != 200:
        return {
            "content": [{"type": "text", "text": "Tell the user there was an error getting locations."}],
            "is_error": True,
        }
    locations = response.json()
    if not locations:
        return {
            "content": [
                {"type": "text", "text": f"Tell the user you could not find any locations matching {args['location_name']}."}
            ]
        }
    for location in locations:
        location.pop("DataSets", None)
    return {"content": [{"type": "text", "text": json.dumps(locations)}]}


@tool(
    "getNext12Hours",
    "Gets the next 12 hours of weather by hour.",
    {"location_key": str, "metric": bool},
)
async def get_next_12_hours(args):
    response = requests.get(
        f"http://dataservice.accuweather.com/forecasts/v1/hourly/12hour/{args['location_key']}",
        params={"apikey": api_key, "metric": args["metric"]},
    )
    if response.status_code != 200:
        return {
            "content": [{"type": "text", "text": "Tell the user there was an error getting the weather."}],
            "is_error": True,
        }
    return {"content": [{"type": "text", "text": json.dumps(response.json())}]}


@tool(
    "getNext5Days",
    "Gets summaries of the next 5 days of weather by day.",
    {"location_key": str, "metric": bool},
)
async def get_next_5_days(args):
    response = requests.get(
        f"http://dataservice.accuweather.com/forecasts/v1/daily/5day/{args['location_key']}",
        params={"apikey": api_key, "metric": args["metric"], "details": True},
    )
    if response.status_code != 200:
        return {
            "content": [{"type": "text", "text": "Tell the user there was an error getting the weather."}],
            "is_error": True,
        }
    return {"content": [{"type": "text", "text": json.dumps(response.json())}]}


weather_tools_server = create_sdk_mcp_server(
    name="weather_tools",
    version="1.0.0",
    tools=[get_location_key, get_next_12_hours, get_next_5_days],
)


def build_weather_agent(model: str):
    @tool(
        "weather_agent",
        "Routes weather questions to a specialized weather agent. Pass the user's request as 'request'.",
        {"request": str},
    )
    async def weather_agent(args):
        text = ""
        async for msg in query(
            prompt=args["request"],
            options=ClaudeAgentOptions(
                system_prompt=WEATHER_AGENT_INSTRUCTIONS,
                mcp_servers={"weather_tools": weather_tools_server},
                allowed_tools=[
                    "mcp__weather_tools__getLocationKey",
                    "mcp__weather_tools__getNext12Hours",
                    "mcp__weather_tools__getNext5Days",
                ],
                tools=[],
                permission_mode="bypassPermissions",
                model=model,
            ),
        ):
            if isinstance(msg, ResultMessage) and msg.subtype == "success":
                text = msg.result
        return {"content": [{"type": "text", "text": text}]}

    return weather_agent
