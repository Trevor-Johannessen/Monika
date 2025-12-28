from dotenv import load_dotenv
load_dotenv()
from fastapi.responses import StreamingResponse
from fastapi import FastAPI
from prompt import Prompt
from io import BytesIO
from voice import Voice
from controller import Controller
import sounddevice as sd
import soundfile as sf

app = FastAPI()
voice = Voice(
    model="0yy6aROli0UmPMyExQ1S",
    directory="/mnt/fs1/media/audio/voice-lines/monika/history"
)
controller = Controller()


filename = 'your_audio.wav'
data, fs = sf.read(filename)



@app.post("/prompt")
async def prompt(data: Prompt):
    print(f"USER> {data.prompt} {data.attributes}")
    if data.return_type == "audio":
        filename = 'your_audio.wav'
        data, fs = sf.read(filename)

        devices = sd.query_devices()
        device_id = None
        for i, dev in enumerate(devices):
            if 'VirtualMic' in dev['name']:
                device_id = i
                break
            sd.play(data, fs, device=device_id)
            sd.wait()
    else:
        pass
