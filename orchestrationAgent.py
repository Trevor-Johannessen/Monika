from agents import Agent, ModelSettings

class OrchestrationAgent(Agent):
    def __init__(self, agents=[], outputType=None):
        super().__init__(
            name="orchestration_agent",
            instructions="Hand off to the apropriate agent based on the request, if it seems like there is nothing more to be done, call the conversation agent. Consider the entire prompt when thinking about what agent to handoff to.",
            handoffs=agents,
            model="gpt-4o-mini",
        )
 