from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
from fastapi import FastAPI
import os
load_dotenv()

# The Claude Agent SDK shells out to the `claude` CLI. Deliberately no
# ANTHROPIC_API_KEY here: that env var takes precedence over the claude.ai
# subscription login and would switch this off pay-per-token API billing.

from prompt import Prompt
from io import BytesIO
from voice import Voice as OpenAIVoice
from voice_elevenlabs import Voice as ElevenLabsVoice
from controller import Controller
from speech import SpeechStream
import asyncio
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
    if data.return_type == "audio" and data.audio_format == "pcm":
        return await stream_prompt(data)
    # Send prompt to orchestrator
    response = await controller.prompt(data)
    if data.return_type == "audio":
        # A blocking ElevenLabs call; keep it off the event loop.
        audio = await asyncio.to_thread(voice.generate_voice, response)
        audio_bytes = BytesIO()
        audio_bytes.write(audio)
        audio_bytes.seek(0)
        return StreamingResponse(audio_bytes, media_type="audio/mpeg")
    else:
        print(f"BOT> {response}") 
        return {"message": response}


async def stream_prompt(data: Prompt):
    """Answer with one ordered PCM body that starts on the first sentence.

    The turn runs as a task and writes sentences into the speech stream as the
    model produces them; the response body is whatever that stream has
    synthesised so far, so playback begins while the model is still working.
    """
    speech = SpeechStream(
        voice,
        directory=settings.get("voice_directory"),
        verbose=settings.get("verbose", False),
    )

    async def run_turn():
        try:
            response = await controller.prompt(data, speech=speech)
            print(f"BOT> {response}")
        except Exception as exc:
            print(f"Turn failed: {exc!r}")
        finally:
            await speech.close()

    asyncio.create_task(run_turn())
    return StreamingResponse(
        speech.chunks(), media_type="audio/L16; rate=24000; channels=1"
    )
