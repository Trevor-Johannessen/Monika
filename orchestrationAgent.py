from agents import Agent, ModelSettings

class OrchestrationAgent(Agent):
    def __init__(self, agents=[], outputType=None):
        super().__init__(
            name="orchestration_agent",
            instructions="""
            You are an orchestration agent apart of a larger ai assistent and chatbot program. You are responsible for orchestrating the order of handoffs between worker agents to complete a task.
            The first thing you should do is think about what information would be needed to fufill the following prompt.
            You should then handoff to the memory agent to query that information.
            Then, you may hand off to the apropriate agent based on the request.
            If the conversation contains information that is relevant to the user or chatbot.
            If it seems like there is nothing more to be done, call the conversation agent.
            """,
            handoffs=agents,
            model="o4-mini",
        )
 
