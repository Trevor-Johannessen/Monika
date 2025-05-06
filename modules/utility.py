from datetime import datetime
import os
from agents import Agent, function_tool

api_key = os.getenv("ACCUWEATHER_API_KEY")

class UtilityAgent(Agent):
    def __init__(self):
        super().__init__(
            name="utility_agent",
            instructions= \
            """You are apart of a larger chatbot. You have the ability to get generally useful data for the client.
                Below are some notes on how to represent data.

                TIME:
                 - Show time in AM/PM format unless otherwise specified.
                 - When showing time date and time, give the minimum amount of information specified.
                 - Format dates using MM/DD/YYYY Syntax
                 - When displaying dates prefer to write out the entire name of the month. 
            """,
            tools=[getDatetime]
        )
    
@function_tool
def getDatetime() -> str:
    """Gets the current date and time"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
    