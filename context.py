from pydantic import BaseModel
from datetime import datetime

class Prompt(BaseModel):
        prompt: str
        response: str
        tools: list[str]
        handoffs: list[str]
        timestamp: datetime

class Context:
    def __init__(self, default_prompt=None):
        self.default_prompt=default_prompt
        self.history=[]
        self.history_head=None

    def setDefaultPrompt(self, prompt):
        self.default_prompt=prompt
        self.history_head = Prompt(
            prompt=self.default_prompt,
            response="",
            tools=[],
            handoffs=[],
            datetime=None
        )
    def addContext(self, context: Prompt):
        self.history.append(context)

    def removeContext(self, i: int):
        self.history.remove(i)

    def clearContext(self):
        self.history=[
            Prompt(prompt=self.default_prompt)
        ]
