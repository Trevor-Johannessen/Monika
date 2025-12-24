"""
    The controller is responseible for setting up all required agents and giving an interface for them to be used. 
"""

from context import Context
from agents import Runner, handoff
from orchestrationAgent import OrchestrationAgent
from conversationAgent import ConversationAgent
from prompt import Prompt
from memoryAgent import MemoryAgent
from modules.weather import WeatherAgent
from modules.spotify import SpotifyAgent
from modules.scheduleTask import ScheduleTaskAgent
from modules.system import SystemAgent

class Controller():

    def __init__(self):
        self.history = Context()
        
        # Import default agent
        agent_list = []
        agent_list.append(ConversationAgent())
        agent_list.append(MemoryAgent())
        agent_list.append(SystemAgent())

        # Import all modules
        agent_list.append(WeatherAgent())
        agent_list.append(SpotifyAgent())
        agent_list.append(ScheduleTaskAgent())

        # Set up the orchestrator
        self.orchestrator = OrchestrationAgent(agents=agent_list)

    async def prompt(self, prompt: Prompt) -> str:
        # Assemble prompt into text
        text = f"{prompt.prompt}\n\nBelow is information that may help with the above prompt. Only use relevant information:\n{prompt.attributes}"

        # Wipe chat if inactive 
        self.history.clean()
        
        # Prompt the orchestrator
        self.history.add(text)
        result = await Runner.run(self.orchestrator, self.history.history)
        self.history.set(result)

        # Return result
        return result.final_output
    
    def getHandoff(self, cls):
        agent = cls()
        if hasattr(agent, 'handoff'):
            return  agent.handoff
        ho = handoff(agent)
        return ho

    
