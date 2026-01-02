from agents import Agent, ModelSettings
from agentModel import AgentModel

class OrchestrationAgent(AgentModel):
    def __init__(self, agents=[], outputType=None):
        super().__init__(
            name="orchestration_agent",
            instructions="""
            You are an chatbot and assistant. Your job is to converse with the user, and use the given tools to execute any request. Please try to be as brief as possible unless otherwise instructed. Do not ackowledge any provided extraneous information. If you require information that has not been provided, use the memory tools to check if that information has been stored elsewhere.
            """,
            tools=[agent.as_tool(agent.name, agent.instructions) for agent in agents],
        )
 
