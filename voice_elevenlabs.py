import os
from datetime import datetime
import shutil
from elevenlabs import ElevenLabs

class Voice():

    def __init__(
        self,
        model="eleven_multilingual_v2",
        directory=None,
        voice="Rachel",
        speed=None,
        instructions="Speak in a neutral tone.",
    ):
        self.client=ElevenLabs()
        self.model=model
        self.voice=voice
        self.instructions=instructions
        self.directory=directory
        self.speed = speed or 1

    def generate_voice(
        self,
        text,
        voice=None,
        model=None,
        instructions=None,
        directory=None,
        speed=None
    ):
        voice = voice or self.voice
        model = model or self.model
        instructions = instructions or self.instructions
        directory = directory or self.directory
        speed = speed or self.speed

        if not self.directory:
            raise Exception("No file path to store audio specified")

        time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{directory}/{time}.mp3"
        filename_temp = f"./{time}.mp3"

        # Generate speech via ElevenLabs API
        audio_iterator = self.client.text_to_speech.convert(
            text=text,
            voice_id=voice,
            model_id=model,
            output_format="mp3_44100_128",
        )

        # Write the streamed audio chunks to a temp file
        with open(filename_temp, "wb") as f:
            for chunk in audio_iterator:
                f.write(chunk)

        # Move the file to the specified drive.
        with open(filename_temp, "rb") as f:
            audio_data = f.read()
            pid = os.fork()
            if pid == 0: # Child process
                shutil.move(filename_temp, filename)
                os._exit(0)
            return audio_data
