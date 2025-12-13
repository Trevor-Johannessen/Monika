from pydantic import BaseModel

class Prompt(BaseModel):
    return_type: str
    attributes: dict
    prompt: str
