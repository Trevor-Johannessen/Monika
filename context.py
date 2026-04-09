from pydantic import BaseModel
from agents import RunResult
from datetime import datetime
import json

class Context:
    def __init__(self, system_text=""):
        self.history = []
        self.last_update = datetime.now()
        self.system_text = system_text
        self.history.append({"role": "system", "content": self._build_system_content()})

    def _realtime_section(self):
        now = datetime.now()
        out = "## Realtime Information\nCurrent date and time: "
        #out += f"\n{now.strftime('%Y-%m-%d %H:%M:%S')}"
        return out

    def _build_system_content(self):
        parts = [self.system_text] if self.system_text else []
        parts.append(self._realtime_section())
        return "\n\n".join(parts)

    def update(self):
        self.history[0]["content"] = self._build_system_content()

    def add(self, text: str, role: str = "user"):
        self.addRaw({"role": role, "content": text})

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
        self.history = []
        self.history.append({"role": "system", "content": self._build_system_content()})

    def clean(self):
        if len(self.history) < 2:
            return
        # Clear history if inactive for 15 minutes
        if (datetime.now() - self.last_update).total_seconds() > 900:
            self.clear()

    def toJson(self):
        return json.dumps(self.toDict())

    def toDict(self):
        return {"last_updated": self.last_update.strftime("%Y-%m-%d %H:%M:%S"), "history": self.history}
