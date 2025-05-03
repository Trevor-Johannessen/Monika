import os
from datetime import datetime
import shutil
from elevenlabs import  save
from elevenlabs.client import ElevenLabs

class Voice():

    def __init__(self, model=None, directory=None):
        api_key=os.environ.get("ELEVENLABS_API_KEY")
        self.elevenlabs = ElevenLabs(api_key=api_key)
        self.model=model
        self.directory=directory
        
    def _save(self, stream):
        if not self.directory:
            raise Exception("No file path to store audio specified")

        time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{self.directory}/{time}.mp3"
        filename_temp = f"./{time}.mp3"
    
        # You HAVE to save the file first beacuase cloning the stream will cause two API calls
        save(stream, filename_temp)
        with open(filename_temp, "rb") as f:
            audio_data = f.read()
            pid = os.fork()
            if pid == 0: # Child process
                shutil.move(filename_temp, filename)
                os._exit(0)
            return audio_data
    
    def generate_voice(self, text, model=None):
        model = model if model else self.model
        if not model:
            raise Exception("No default model nor any model provided")

        audio_stream = self.elevenlabs.text_to_speech.convert(
            text=text,
            voice_id=model,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128"
        )
        audio = self._save(audio_stream)
        return audio
