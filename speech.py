"""Turn model text into speech while the model is still writing it.

One turn produces one ordered PCM stream: text deltas go into a
SentenceSplitter, whole sentences go to a SpeechStream, and the PCM the TTS
returns for each one is appended to an asyncio.Queue that the HTTP response
body drains. Playback therefore starts on the first sentence instead of after
the last one.
"""

import asyncio
import os
import re
import subprocess
import time
import wave
from datetime import datetime

SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2
CHANNELS = 1

# An optional "[mood]" tag the model may put at the very start of a reply, so
# the Buddy sprite matches what is being said without costing a tool call.
_MOOD_RE = re.compile(r"^\[([A-Za-z_][A-Za-z_-]*)\]\s*")
# Past this many characters a leading "[" is clearly not a mood tag.
_MOOD_MAX = 24

_SENTENCE_END = ".!?"


def strip_mood_tag(text):
    """Split a leading "[mood]" tag off a finished reply.

    Returns (mood or None, text). Text callers never see the tag.
    """
    match = _MOOD_RE.match(text or "")
    if not match:
        return None, text
    return match.group(1).lower(), text[match.end():]


def pcm_seconds(pcm_bytes):
    return pcm_bytes / float(SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)


class SentenceSplitter:
    """Accumulate text deltas and hand back whole sentences.

    A sentence ends at . ! or ? followed by whitespace, or at a flush. The
    leading mood tag is consumed before the first sentence is emitted and left
    on `mood`.
    """

    def __init__(self):
        self._buf = ""
        self.mood = None
        self._mood_done = False

    def feed(self, text):
        """Add a text delta; return the sentences that are now complete."""
        self._buf += text or ""
        if not self._consume_mood():
            return []
        out = []
        while True:
            end = self._sentence_end()
            if end is None:
                break
            sentence = self._buf[:end].strip()
            self._buf = self._buf[end:].lstrip()
            if sentence:
                out.append(sentence)
        return out

    def flush(self):
        """Emit whatever is left, finished or not."""
        self._mood_done = True
        self._consume_mood()
        rest = self._buf.strip()
        self._buf = ""
        return [rest] if rest else []

    def _consume_mood(self):
        """True once the leading tag is dealt with and the buffer is speakable."""
        if self._mood_done:
            return True
        stripped = self._buf.lstrip()
        if not stripped:
            return False
        if not stripped.startswith("["):
            self._buf = stripped
            self._mood_done = True
            return True
        match = _MOOD_RE.match(stripped)
        if match:
            self.mood = match.group(1).lower()
            self._buf = stripped[match.end():]
            self._mood_done = True
            return True
        # A bracket that turned out not to be a tag: speak it as written.
        if "]" in stripped or len(stripped) > _MOOD_MAX:
            self._buf = stripped
            self._mood_done = True
            return True
        return False  # still waiting for the closing bracket

    def _sentence_end(self):
        """Index just past the terminator of the first complete sentence."""
        for i, ch in enumerate(self._buf):
            if ch not in _SENTENCE_END:
                continue
            # Run through "?!" and any closing quote or bracket.
            j = i + 1
            while j < len(self._buf) and self._buf[j] in _SENTENCE_END:
                j += 1
            while j < len(self._buf) and self._buf[j] in '"\')]':
                j += 1
            if j >= len(self._buf):
                return None  # might still be mid-terminator
            if self._buf[j].isspace():
                return j
        return None


class SpeechStream:
    """An ordered sentence -> PCM pipeline for one turn.

    Sentences are synthesised one at a time, in the order they were submitted,
    so the room hears the reply in the order it was written. Chunks land on
    `_out` as they arrive from the TTS; the HTTP response body iterates them.
    """

    def __init__(self, voice, directory=None, verbose=False, agent="monika"):
        self._voice = voice
        self._directory = directory
        self._verbose = verbose
        self._agent = agent
        self._in = asyncio.Queue()
        self._out = asyncio.Queue()
        self._parts = []
        self._closed = False
        self._first_chunk_at = None
        # (sentence, offset in seconds where its audio starts), so an
        # interruption can tell roughly how far into the reply the room got.
        self._timeline = []
        self._aborted = False
        self._buddy_shown = False
        self.mood = None
        self._worker = asyncio.create_task(self._run())

    def say(self, text):
        """Queue one sentence. Safe to call from a tool or the turn loop."""
        text = (text or "").strip()
        if text and not self._closed:
            self._in.put_nowait(text)

    async def close(self):
        """No more sentences; wait for the queued ones to finish speaking."""
        if self._closed:
            return
        self._closed = True
        self._in.put_nowait(None)
        await self._worker

    def abort(self):
        """Stop speaking now. Returns the sentences the room has started hearing.

        Hearing is estimated from the wall clock since the first chunk went out:
        the speaker plays in real time, so anything whose audio starts after
        that point never made it into the room.
        """
        elapsed = 0.0
        if self._first_chunk_at is not None:
            elapsed = time.monotonic() - self._first_chunk_at
        heard = [text for text, start in self._timeline
                 if self._first_chunk_at is not None and start < elapsed]
        if not self._aborted:
            self._aborted = True
            self._closed = True
            while not self._in.empty():
                self._in.get_nowait()
            self._in.put_nowait(None)
        return heard

    async def chunks(self):
        """Async-iterate the PCM for the HTTP response body."""
        while True:
            chunk = await self._out.get()
            if chunk is None:
                return
            yield chunk

    @property
    def audio_seconds(self):
        return pcm_seconds(sum(len(p) for p in self._parts))

    async def _run(self):
        previous = None
        while True:
            text = await self._in.get()
            if text is None:
                break
            if self._aborted:
                break
            try:
                await self._speak(text, previous)
            except Exception as exc:  # a failed sentence must not end the turn
                print(f"Could not speak {text!r}: {exc}")
            previous = text
        self._out.put_nowait(None)
        await self._finish()

    async def _speak(self, text, previous):
        if not self._buddy_shown:
            self._buddy_shown = True
            self._buddy("show", self.mood or "neutral", 30.0)
        loop = asyncio.get_running_loop()
        self._timeline.append((text, self.audio_seconds))

        def pump():
            for chunk in self._voice.stream_pcm(text, previous_text=previous):
                if self._aborted:
                    break
                if not chunk:
                    continue
                if self._first_chunk_at is None:
                    self._first_chunk_at = time.monotonic()
                self._parts.append(chunk)
                loop.call_soon_threadsafe(self._out.put_nowait, chunk)

        await asyncio.to_thread(pump)

    async def _finish(self):
        """Correct Buddy's guessed duration and archive the turn as one WAV."""
        if self._buddy_shown and self._aborted:
            self._buddy("hide")
        elif self._buddy_shown:
            played = 0.0
            if self._first_chunk_at is not None:
                played = time.monotonic() - self._first_chunk_at
            remaining = self.audio_seconds - played
            if remaining > 1.0:
                self._buddy("show", self.mood or "neutral", remaining)
            else:
                self._buddy("hide")
        if self._directory and self._parts:
            try:
                await asyncio.to_thread(self._write_wav)
            except OSError as exc:
                print(f"Could not save the voice line: {exc}")

    def _write_wav(self):
        name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(self._directory, f"{name}.wav")
        with wave.open(path, "wb") as out:
            out.setnchannels(CHANNELS)
            out.setsampwidth(SAMPLE_WIDTH)
            out.setframerate(SAMPLE_RATE)
            out.writeframes(b"".join(self._parts))

    def _buddy(self, command, mood=None, seconds=None):
        """Put the sprite up (or take it down) without blocking the audio."""
        if command == "hide":
            argv = ["buddy", "hide"]
        else:
            argv = ["buddy", "show", mood, "--mode", "speech",
                    "--audio-seconds", f"{seconds:.1f}", "--agent", self._agent]

        def run():
            try:
                subprocess.run(argv, capture_output=True, timeout=10)
            except Exception as exc:
                if self._verbose:
                    print(f"buddy failed: {exc}")

        asyncio.get_running_loop().run_in_executor(None, run)
