from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
from fastapi import FastAPI
import os
from credentials import read_key
load_dotenv()

# The Claude Agent SDK shells out to the `claude` CLI, which authenticates via the
# ANTHROPIC_API_KEY environment variable (inherited by any subprocesses it spawns),
# so this one key must live in the environment. Load it explicitly from the file.
_anthropic_key = read_key("anthropic.key")
if _anthropic_key:
    os.environ["ANTHROPIC_API_KEY"] = _anthropic_key

from prompt import Prompt
from io import BytesIO
from voice import Voice as OpenAIVoice
from voice_elevenlabs import Voice as ElevenLabsVoice
from controller import Controller
import dashboard
import json


with open('defaults.json', 'r') as f:
    defaults = json.load(f)
settings = {}
if os.path.exists('settings.json'):
    with open('settings.json', 'r') as f:
        settings = json.load(f)
settings = {**defaults, **settings}

if settings['verbose']:
    print("SETTINGS:")
    print(settings)

app = FastAPI()
Voice = ElevenLabsVoice if settings['voice_provider'] == 'elevenlabs' else OpenAIVoice
voice = Voice(
    voice=settings['voice_name'],
    directory=settings['voice_directory'],
    speed = settings['voice_speed']
)
controller = Controller(settings, voice)
dashboard.register(app, voice_directory=settings.get('voice_directory'))

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
