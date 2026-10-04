from pydantic import BaseModel

class Prompt(BaseModel):
    prompt: str
    return_type: str = "text"
    # "pcm" asks for one streamed 24 kHz mono s16 body that starts before the
    # reply is finished; "mp3" is the whole clip in one piece.
    audio_format: str = "mp3"
    attributes: dict = {}
    # The user spoke over the reply in flight: stop it, and answer this instead.
    interrupt: bool = False
