from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
load_dotenv()
from fastapi import FastAPI
from prompt import Prompt
from io import BytesIO
from voice import Voice
from controller import Controller

app = FastAPI()
voice = Voice(
    model="0yy6aROli0UmPMyExQ1S",
    directory="/mnt/fs1/media/audio/voice-lines/monika/history"
)
controller = Controller()

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
