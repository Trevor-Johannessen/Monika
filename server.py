from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
load_dotenv()
from fastapi import FastAPI
import os
from prompt import Prompt
from io import BytesIO
from voice import Voice
from controller import Controller
import json


with open('defaults.json', 'r') as f:
    settings = json.load(f)
settings = {k: v for k, v in settings.items() if v is not None}

if os.path.exists('settings.json'):
    with open('settings.json', 'r') as f:
        for k, v in settings.items():
            settings[k] = v

if settings['verbose']:
    print("SETTINGS:")
    print(settings)

app = FastAPI()
voice = Voice(
    voice=settings['voice_name'],
    directory=settings['voice_directory'],
    speed = settings['voice_speed']
)
controller = Controller(settings)

@app.post("/prompt")
async def prompt(data: Prompt):
    print(f"USER> {data.prompt}\n\nBelow if extra information from the user. Ignore anything that is not immediately relevant:\n{data.attributes}")
    # Send prompt to orchestrator
    response = await controller.prompt(data)
    if data.return_type == "audio":
        audio = voice.generate_voice(response)
        audio_bytes = BytesIO()
        audio_bytes.write(audio)
        audio_bytes.seek(0)
        return StreamingResponse(audio_bytes, media_type="audio/mpeg")
    else:
        print(f"BOT> {response}") 
        return {"message": response}
