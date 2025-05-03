"""
    The controller is responseible for setting up all required agents and giving an interface for them to be used. 
"""

from orchestrator import OrchestrationAgent
from conversationAgent import ConversationAgent
from agents import Runner
class Controller():

    def __init__(self):
        agent_list = []
        # Import default agent
        agent_list.append(ConversationAgent())

        # Import all modules

        # Set up the orchestrator
        self.orchestrator = OrchestrationAgent(agents=agent_list)

    async def prompt(self, text) -> str:
        result = await Runner.run(self.orchestrator, text)
        return result.final_output

    
