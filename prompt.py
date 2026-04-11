from pydantic import BaseModel

class Prompt(BaseModel):
    prompt: str
    return_type: str = "text"
    attributes: dict = {}
