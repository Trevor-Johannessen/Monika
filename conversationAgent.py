from agents import Agent

class ConversationAgent(Agent):
    def __init__(self):
        super().__init__(
            name="conversation_agent",
            instructions="You are a home assistant chatbot. You are responsible for conversing with the user. This chatbot also has the ability to call functions, if you see a function has just been called, please response with a related message.",
        )