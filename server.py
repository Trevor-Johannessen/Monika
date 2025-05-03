from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from voice import Voice
class Prompt(BaseModel):
    return_type: str
    prompt: str

load_dotenv()

app = FastAPI()
voice = Voice(
    model="0yy6aROli0UmPMyExQ1S",
    directory="/mnt/fs1/media/audio/voice-lines/monika/history"
)

@app.post("/prompt")
async def read_root(data: Prompt):
    # Send prompt to orchestrator
    
    return {"message": f"Content: {data.return_type}, prompt: {data.prompt}"}