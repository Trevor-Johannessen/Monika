from agents import Agent, ModelSettings

class AgentModel(Agent):
    def __init__(self, settings={}, **kwargs):
        super().__init__(
            model=settings['default_model'] if 'default_model' in settings else 'gpt-4.1-nano',
            **kwargs
        )
