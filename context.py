from pydantic import BaseModel
from agents import RunResult
from datetime import datetime
import json

class Context:
    def __init__(self):
        self.history=[]
        self.last_update = datetime.now()
        self.system_text = ""
        
    def add(self, text: str, role: str = "user"):
        self.addRaw({"role":role,"content":text})

    def addRaw(self, result: dict):
        self.history.append(result)
        self.last_update = datetime.now()

    def set(self, context: RunResult):
        self.history = context.to_input_list()
        self.last_update = datetime.now()

    def remove(self, i: int = -1):
        if len(self.history) > 0:
            self.history.remove(i)

    def clear(self):
        self.history=[]

    def clean(self):
        if len(self.history) < 1:
            return
        # Clear history if inactive for 15 minutes
        if (datetime.now() - self.last_update).total_seconds() > 900: 
            self.clear()
    
    def toJson(self):
        return json.dumps(self.toDict())

    def toDict(self):
        return {"last_updated": self.last_update.strftime("%Y-%m-%d %H:%M:%S"), "history": self.history}
