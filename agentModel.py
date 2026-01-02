from agents import Agent, ModelSettings

class AgentModel(Agent):
    def __init__(self, **kwargs):
        super().__init__(
            model="gpt-5-nano",
            **kwargs
        )
