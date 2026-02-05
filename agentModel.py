from agents import Agent, ModelSettings

class AgentModel(Agent):
    def __init__(self, settings={}, **kwargs):
        super().__init__(
            model=settings['default_model'],
            **kwargs
        )
