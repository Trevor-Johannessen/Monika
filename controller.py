"""
    The controller is responseible for setting up all required agents and giving an interface for them to be used.
"""

import requests
from datetime import datetime
from context import Context
from orchestrationAgent import OrchestrationAgent
from prompt import Prompt
from modules.memoryAgent import MemoryAgent
from modules.weather import WeatherAgent
from modules.spotify import SpotifyAgent
from modules.scheduleTask import ScheduleTaskAgent


class Controller():

    def __init__(self, settings):
        self.settings = settings
        inital_prompt = settings['inital_prompt'] if 'inital_prompt' in settings else ""
        self.history = Context(inital_prompt)

        # Import all modules
        agent_list = []
        #agent_list.append(MemoryAgent(settings=self.settings))
        agent_list.append(WeatherAgent(settings=self.settings))
        agent_list.append(SpotifyAgent(settings=self.settings))
        #agent_list.append(ScheduleTaskAgent(settings=self.settings))

        # Set up webhooks
        self.webhooks = settings['webhooks']

        # Set up the orchestrator
        self.orchestrator = OrchestrationAgent(agents=agent_list, settings=settings)

    def update_webhook(self):
        #requests.post(self.webhooks[0], json=self.history.toDict())#, headers={"Content-Type": "application/json"})
        list(map(lambda url: self.post_webhook(url, self.history.toDict()), self.webhooks))

    def post_webhook(self, endpoint, message):
        try:
            requests.post(endpoint, json=message)
        except Exception:
            if self.settings['verbose']:
                print(f"Could not update {endpoint}")

    async def prompt(self, prompt: Prompt) -> str:
        # Add default attributes
        prompt.attributes['time'] = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S") if 'time' not in prompt.attributes else prompt.attributes['time']

        # Add prompt to context
        text = f"{prompt.prompt}\n\nBelow is information that may help with the above prompt. Only use relevant information:\n{prompt.attributes}"
        self.history.clean()
        self.history.add(text)

        # Update webhook for prompt
        self.update_webhook()

        # Prompt the orchestrator
        time_start = datetime.now()
        result, messages = await self.orchestrator.run(self.history.history)
        self.history.set(messages)
        time_end = datetime.now()
        time_delta = time_end - time_start

        # Report stats if required
        if self.settings['verbose']:
            print(f"Response took {time_delta.total_seconds()} seconds.")

        # Update webhook for response
        self.update_webhook()

        # Return result
        return result
