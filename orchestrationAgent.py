from agents import Agent, ModelSettings

class OrchestrationAgent(Agent):
    def __init__(self, agents=[], outputType=None):
        super().__init__(
            name="orchestration_agent",
            instructions="""
            You are an orchestration agent apart of a larger ai assistent and chatbot program. You are responsible for orchestrating the order of handoffs between worker agents to complete a task. If there is nothing left to do you should respond to the user. Please try to be as brief as possible unless otherwise instructed. Omit any details that are not relevant to the user. 
            The first thing you should do is think about what information would be needed to fufill the following prompt.
            You should then handoff to the memory agent to query that information.
            Then, you may hand off to the apropriate agent based on the request.
            If the conversation contains information that is relevant to the user or chatbot.
            """,
            tools=[agent.as_tool(agent.name, agent.instructions) for agent in agents],
            model="gpt-5-nano",
        )
 
