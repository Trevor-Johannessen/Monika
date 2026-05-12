"""
    The controller is responseible for setting up all required agents and giving an interface for them to be used.
"""

import os
import requests
from datetime import datetime
from context import Context
from orchestrationAgent import OrchestrationAgent
from prompt import Prompt
from modules.memoryAgent import MemoryAgent
from modules.weather import WeatherAgent
from modules.scheduleTask import ScheduleTaskAgent
from modules.claudeCode import ClaudeCodeAgent
from modules.steam import SteamAgent
#from modules.minecraft import MinecraftAgent

REMINDERS_DIR = "/etc/monika/reminders"


VOICE_INSTRUCTION = (
    "\n\nIMPORTANT: Respond using complete words only. Do not use any special characters "
    "such as &, *, #, @, or degree symbols. Write out all units and measurements as words "
    "(e.g. \"degrees\" not \"°\", \"and\" not \"&\", \"percent\" not \"%\")."
)


class Controller():

    def __init__(self, settings):
        self.settings = settings
        inital_prompt = settings['inital_prompt'] if 'inital_prompt' in settings else ""
        self.history = Context(inital_prompt)

        # Import all modules
        agent_list = []
        #agent_list.append(MemoryAgent(settings=self.settings))
        agent_list.append(WeatherAgent(settings=self.settings))
        agent_list.append(ClaudeCodeAgent(settings=self.settings))
        agent_list.append(SteamAgent(settings=self.settings))
        #agent_list.append(MinecraftAgent(settings=self.settings))
        #agent_list.append(ScheduleTaskAgent(settings=self.settings))

        # Set up webhooks
        self.webhooks = settings['webhooks']

        # Set up the orchestrator
        self.orchestrator = OrchestrationAgent(agents=agent_list, settings=settings, context=self.history)

    def update_webhook(self):
        #requests.post(self.webhooks[0], json=self.history.toDict())#, headers={"Content-Type": "application/json"})
        list(map(lambda url: self.post_webhook(url, self.history.toDict()), self.webhooks))

    def post_webhook(self, endpoint, message):
        try:
            requests.post(endpoint, json=message)
        except Exception:
            if self.settings['verbose']:
                print(f"Could not update {endpoint}")

    def _load_pending_reminders(self) -> str:
        if not os.path.isdir(REMINDERS_DIR):
            return ""
        blocks = []
        for name in sorted(os.listdir(REMINDERS_DIR)):
            path = os.path.join(REMINDERS_DIR, name)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r") as f:
                    body = f.read().strip()
            except OSError:
                continue
            blocks.append(f"File: {name}\n{body}")
        return "\n\n".join(blocks)

    async def prompt(self, prompt: Prompt) -> str:
        # Add default attributes
        prompt.attributes['time'] = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S") if 'time' not in prompt.attributes else prompt.attributes['time']

        # Add prompt to context
        text = f"{prompt.prompt}\n\nBelow is information that may help with the above prompt. Only use relevant information:\n{prompt.attributes}"
        reminders_text = self._load_pending_reminders()
        if reminders_text:
            text += (
                "\n\nPending reminders (evaluate each Trigger against the current time and the user's message; "
                "if fired, surface the message to the user and delete the file; otherwise ignore silently):\n"
                + reminders_text
            )
        self.history.clean()
        self.history.add(text)

        # Update webhook for prompt
        self.update_webhook()

        # Prompt the orchestrator
        time_start = datetime.now()
        if prompt.return_type == "audio" and self.history.history:
            run_history = list(self.history.history)
            original_last = run_history[-1]
            modified_last = dict(original_last)
            modified_last["content"] = modified_last["content"] + VOICE_INSTRUCTION
            run_history[-1] = modified_last
            result, messages = await self.orchestrator.run(run_history)
            messages[len(self.history.history) - 1] = original_last
        else:
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
