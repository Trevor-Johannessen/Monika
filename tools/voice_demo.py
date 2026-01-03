from dotenv import load_dotenv
load_dotenv()
from voice import Voice

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
        v.generate_voice(msg, voice=voices[voice_id], instructions=instructions, directory=output_dir)
