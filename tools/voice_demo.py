from dotenv import load_dotenv
load_dotenv()
import argparse
import os
import requests
from voice import Voice

parser = argparse.ArgumentParser()
parser.add_argument('--playback-server', type=str, default=None, help='URI to POST mp3 to (e.g. speaker.server:1234/play)')
args = parser.parse_args()

v = Voice(directory='./')

voices = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
]

msg = ""
voice_id=0
instructions=None
output_dir=None
help_messages = ["", "help"]

#msg = input("Enter message. Type 'help' for help: ")
while True:
    msg = input("Enter message. Type 'help' for help: ")

    if msg.isdigit():
        voice_id = int(msg)
        print(f"Changed voice to {voices[voice_id]}.")
    elif msg == 'instructions':
        instructions = input("instructions: ")
    elif msg in ['output', 'out']:
        output_dir = input("output dir: ")
    elif msg in help_messages:
        print("Type 'instructions' to set new instructions.\nType 'output' to set an output directory.\nType a digit to set a new voice id.\nVoice IDs:")
        for i in range(0, len(voices)):
            print(f"{i}: {voices[i]}")
    else:
        audio_data = v.generate_voice(msg, voice=voices[voice_id], instructions=instructions, directory=output_dir)
        #audio_data = v.generate_voice(msg, voice=voice, instructions=instructions, directory=output_dir)
        #tmpfile = f"/mnt/fs1/media/audio/voice-lines/openai/{voice}-{msg}.mp3"
        tmpfile = f"/mnt/fs1/media/audio/voice-lines/openai/{voices[voice_id]}-{msg[:30]}.mp3"
        with open(tmpfile, "wb") as f:
            f.write(audio_data)
        if args.playback_server:
            url = f"http://{args.playback_server}"
            with open(tmpfile, "rb") as f:
                requests.post(url, files={"file": ("speech.mp3", f, "audio/mpeg")})
        
