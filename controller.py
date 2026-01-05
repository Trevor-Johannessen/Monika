"""
    The controller is responseible for setting up all required agents and giving an interface for them to be used. 
"""

import requests
from context import Context
from agents import Runner, handoff
from orchestrationAgent import OrchestrationAgent
from prompt import Prompt
from modules.memoryAgent import MemoryAgent
from modules.weather import WeatherAgent
from modules.spotify import SpotifyAgent
from modules.scheduleTask import ScheduleTaskAgent
from modules.system import SystemAgent

class Controller():

    def __init__(self, settings):
        self.history = Context()

        # Import all modules
        agent_list = []
        agent_list.append(MemoryAgent())
        agent_list.append(SystemAgent())
        agent_list.append(WeatherAgent())
        agent_list.append(SpotifyAgent())
        agent_list.append(ScheduleTaskAgent())

        # Set up webhooks
        self.webhooks = settings['webhooks'] if "webhooks" in settings else []

        # Set up the orchestrator
        self.orchestrator = OrchestrationAgent(agents=agent_list)

    def update_webhook(self):
        #requests.post(self.webhooks[0], json=self.history.toDict())#, headers={"Content-Type": "application/json"})
        list(map(lambda url: requests.post(url, json=self.history.toDict()), self.webhooks))

    async def prompt(self, prompt: Prompt) -> str:
        # Add prompt to context
        text = f"{prompt.prompt}\n\nBelow is information that may help with the above prompt. Only use relevant information:\n{prompt.attributes}"
        self.history.clean()
        self.history.add(text)

        # Update webhook for prompt        
        self.update_webhook()

        # Prompt the orchestrator
        result = await Runner.run(self.orchestrator, self.history.history)
        self.history.set(result)

        # Update webhook for response
        self.update_webhook()

        # Return result
        return result.final_output
    
    def getHandoff(self, cls):
        agent = cls()
        if hasattr(agent, 'handoff'):
            return  agent.handoff
        ho = handoff(agent)
        return ho

    
