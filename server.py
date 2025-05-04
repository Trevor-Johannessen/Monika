from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from voice import Voice
from controller import Controller

class Prompt(BaseModel):
    return_type: str
    prompt: str

load_dotenv()

app = FastAPI()
voice = Voice(
    model="0yy6aROli0UmPMyExQ1S",
    directory="/mnt/fs1/media/audio/voice-lines/monika/history"
)
controller = Controller()

@app.post("/prompt")
async def prompt(data: Prompt):
    # Send prompt to orchestrator
    response = await controller.prompt(data.prompt)
    return {"message": response}