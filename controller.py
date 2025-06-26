"""
    The controller is responseible for setting up all required agents and giving an interface for them to be used. 
"""

from removeReasoningItems import removeReasoningItems
from context import Context
from agents import Runner, handoff
from orchestrationAgent import OrchestrationAgent
from conversationAgent import ConversationAgent
from modules.NoteAgent import NoteAgent
from modules.scheduleTask import ScheduleTaskAgent
from modules.spotify import SpotifyAgent
from modules.utility import UtilityAgent
from modules.weather import WeatherAgent

class Controller():

    def __init__(self):
        self.history = Context()
        
        # Import default agent
        agent_list = []
        agent_list.append(self.getHandoff(ConversationAgent))

        # Import all modules

        # Set up the orchestrator
        self.orchestrator = OrchestrationAgent(agents=agent_list)

    async def prompt(self, text) -> str:

        # Append user message
        self.history.clean()
        self.history.add(text)
        
        # Generate results.
        result = await Runner.run(self.orchestrator, self.history.history)
        self.history.set(result)

        # Return result
        return result.final_output
    
    def getHandoff(self, cls):
        agent = cls()
        if hasattr(agent, 'handoff'):
            return  agent.handoff
        return agent

    
