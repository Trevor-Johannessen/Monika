from datetime import datetime
import os
from agents import Agent, function_tool, ModelSettings

class UtilityAgent(Agent):
    def __init__(self):
        super().__init__(
            name="utility_agent",
            instructions= \
            """You are apart of a larger chatbot. You have the ability to get generally useful data for the client. You may also be used to get contextual information for other Agents.
                Below are some notes on how to represent data.

                TIME:
                 - Show time in AM/PM format unless otherwise specified.
                 - When showing time date and time, give the minimum amount of information specified.
                 - Format dates using MM/DD/YYYY Syntax
                 - When displaying dates prefer to write out the entire name of the month. 
            """,
            tools=[getDatetime],
            model_settings=ModelSettings(tool_choice="required"),
            model='o4-mini'
        )
    
@function_tool
def getDatetime() -> str:
    """Gets the current date and time"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
    