"""
    The controller is responseible for setting up all required agents and giving an interface for them to be used. 
"""

from context import Context
from agents import Runner
from orchestrationAgent import OrchestrationAgent
from conversationAgent import ConversationAgent


class Controller():

    def __init__(self):
        self.history = Context()
        
        # Import default agent
        agent_list = []
        agent_list.append(ConversationAgent())

        # Import all modules

        # Set up the orchestrator
        self.orchestrator = OrchestrationAgent(agents=agent_list)

    async def prompt(self, text) -> str:

        # Append user message
        self.history.clean()
        self.history.add(text)

        result = await Runner.run(self.orchestrator, self.history.history)
        
        # Add result to chat history
        self.history.set(result)

        # Return result
        return result.final_output

    
