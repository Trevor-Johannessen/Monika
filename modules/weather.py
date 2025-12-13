from datetime import datetime
import os
import requests
from agents import Agent, function_tool

api_key = os.getenv("ACCUWEATHER_API_KEY")

class WeatherAgent(Agent):
    def __init__(self):
        super().__init__(
            name="weather_agent",
            instructions="You are a meteorologist apart of a larger home assistant chatbot. Your job is to get weather about given places and give a summary of relevant information. Assume the user only wants the current weather conditions unless otherwise specified. You have tools to help get the weather via the AccuWeather API. Answer only in plaintext and do not provide any links. Do not use Markdown or any other stylings. Any sources used should not be stated. Answer in Imperial units unless otherwise specified. Default to the shortest timespan available unless otherwise specified. Ignore any information that isn't specified by the prompt except percipitation. Mention rain or snow if there is any.",
            tools=[getLocationKey, getNext12Hours, getNext5Days]
        )

@function_tool
def getLocationKey(location_name: str) -> dict:
    """Gets the location key of a given town or city by name. Returns a list of cities and additional information about them. The location key is stored in the 'Key' attribute.
    
        Args:
            location_name: The name of the location to get the weather at.
    """
    response = requests.get(
        f"http://dataservice.accuweather.com/locations/v1/cities/search",
        params={
            "apikey": api_key,
            "q": location_name
        }
    )
    # Error handling
    if response.status_code != 200:
        return "Tell the user there was an error getting locations."
    locations = response.json()
    if len(locations) == 0:
        return f"Tell the user you could not find any locations matching {location_name}."
    
    # Trim excess information
    for location in locations:
        del location['DataSets']

    return locations

@function_tool
def getNext12Hours(location_key: str, metric: bool) -> dict:
    """Gets the next 12 hours of weather by hour.
    
        Args:
            location_key: The AccuWeather location key of the city to get the weather from.
            metric: Controller if units are in metric (Default = False).
    """
    response = requests.get(
        f"http://dataservice.accuweather.com/forecasts/v1/hourly/12hour/{location_key}",
        params={
            "apikey": api_key,
            "metric": metric
        }
    )
    if response.status_code != 200:
        return "Tell the user there was an error getting the weather."
    return response.json()
    
@function_tool
def getNext5Days(location_key: str, metric: bool) -> dict:
    """Gets summaries of the next 5 days of weather by day.
    
        Args:
            location_key: The AccuWeather location key of the city to get the weather from.
            metric: Controller if units are in metric (Default = False).
    """
    response = requests.get(
        f"http://dataservice.accuweather.com/forecasts/v1/daily/5day/{location_key}",
        params={
            "apikey": api_key,
            "metric": metric,
            "details": True
        }
    )
    if response.status_code != 200:
        return "Tell the user there was an error getting the weather."
    return response.json()
