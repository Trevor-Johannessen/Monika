from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
load_dotenv()
from fastapi import FastAPI
from pydantic import BaseModel
from io import BytesIO
from voice import Voice
from controller import Controller

class Prompt(BaseModel):
    return_type: str
    prompt: str
    attributes: dict

app = FastAPI()
voice = Voice(
    model="0yy6aROli0UmPMyExQ1S",
    directory="/mnt/fs1/media/audio/voice-lines/monika/history"
)
controller = Controller()

@app.post("/prompt")
async def prompt(data: Prompt):
    # Append attributes to prompt
    pairs = [f"{key}: {data.attributes[key]}" for key in data.attributes.keys()]
    if len(data.attributes) > 0:
        data.prompt += f"\n\nBelow is a list of attributes that may in fufilling the prompt:\n{'\n'.join(pairs)}"

    # Send prompt to orchestrator
    response = await controller.prompt(data.prompt)
    if data.return_type == "audio":
        audio = voice.generate_voice(response)
        audio_bytes = BytesIO()
        audio_bytes.write(audio)
        audio_bytes.seek(0)
        return StreamingResponse(audio_bytes, media_type="audio/mpeg")
    else:
        return {"message": response}