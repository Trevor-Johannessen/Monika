import os
from datetime import datetime
import shutil
from openai import OpenAI

class Voice():

    def __init__(
        self,
        model="gpt-4o-mini-tts",
        directory=None,
        voice="alloy",
        instructions="Speak in a neutral tone."
    ):
        self.client=OpenAI()
        self.model=model
        self.voice=voice
        self.instructions=instructions
        self.directory=directory
        
    def generate_voice(
        self,
        text,
        voice=None,
        model=None,
        instructions=None,
        directory=None
    ):
        voice = voice or self.voice
        model = model or self.model
        instructions = instructions or self.instructions
        directory = directory or self.directory

        if not self.directory:
            raise Exception("No file path to store audio specified")

        time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{directory}/{time}.mp3"
        filename_temp = f"./{time}.mp3"
    

        # Save the text to speech audio
        with self.client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            input=text,
            instructions=instructions,
        ) as response:
            response.stream_to_file(filename_temp)

        # Move the file to the specified drive.
        with open(filename_temp, "rb") as f:
            audio_data = f.read()
            pid = os.fork()
            if pid == 0: # Child process
                shutil.move(filename_temp, filename)
                os._exit(0)
            return audio_data

