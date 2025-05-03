from agents import Agent

class OrchestrationAgent(Agent):
    def __init__(self, agents=[]):
        super().__init__(
            name="orchestration_agent",
            instructions="Hand off to the apropriate agent based on the request, if it seems like there is nothing more to be done, call the conversation agent.",
            handoffs=agents
        )
