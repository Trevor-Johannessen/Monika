"""Sentence splitting and mood-tag handling, the two pure pieces of speech.py."""

import asyncio
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from speech import SentenceSplitter, SpeechStream, pcm_seconds, strip_mood_tag


def feed_all(splitter, deltas):
    out = []
    for delta in deltas:
        out += splitter.feed(delta)
    out += splitter.flush()
    return out


class SentenceSplitterTests(unittest.TestCase):

    def test_emits_on_the_terminator_not_at_the_end(self):
        s = SentenceSplitter()
        self.assertEqual(s.feed("Hello there. "), ["Hello there."])
        self.assertEqual(s.feed("Still going"), [])
        self.assertEqual(s.flush(), ["Still going"])

    def test_a_terminator_split_across_deltas(self):
        s = SentenceSplitter()
        self.assertEqual(s.feed("It is cold"), [])
        self.assertEqual(s.feed("."), [])
        self.assertEqual(s.feed(" Wrap up warm."), ["It is cold."])
        self.assertEqual(s.flush(), ["Wrap up warm."])

    def test_several_sentences_in_one_delta(self):
        s = SentenceSplitter()
        self.assertEqual(
            feed_all(s, ["One. Two! Three? Four"]),
            ["One.", "Two!", "Three?", "Four"],
        )

    def test_terminator_runs_and_closing_quotes_stay_attached(self):
        s = SentenceSplitter()
        self.assertEqual(
            feed_all(s, ['He said "go now!" Then he left.']),
            ['He said "go now!"', "Then he left."],
        )

    def test_decimals_and_abbreviations_do_not_split(self):
        # A terminator only ends a sentence when whitespace follows it.
        s = SentenceSplitter()
        self.assertEqual(feed_all(s, ["It is 21.5 degrees outside."]),
                         ["It is 21.5 degrees outside."])

    def test_flush_on_an_empty_buffer_emits_nothing(self):
        s = SentenceSplitter()
        self.assertEqual(s.feed("Done. "), ["Done."])
        self.assertEqual(s.flush(), [])

    def test_whitespace_only_input(self):
        s = SentenceSplitter()
        self.assertEqual(feed_all(s, ["   ", "\n"]), [])


class MoodTagTests(unittest.TestCase):

    def test_tag_is_stripped_and_recorded(self):
        s = SentenceSplitter()
        self.assertEqual(feed_all(s, ["[weather] It is raining."]),
                         ["It is raining."])
        self.assertEqual(s.mood, "weather")

    def test_tag_arriving_one_character_at_a_time(self):
        s = SentenceSplitter()
        out = feed_all(s, list("[happy] All done."))
        self.assertEqual(out, ["All done."])
        self.assertEqual(s.mood, "happy")

    def test_nothing_is_emitted_while_the_tag_is_incomplete(self):
        s = SentenceSplitter()
        self.assertEqual(s.feed("[exc"), [])
        self.assertIsNone(s.mood)
        self.assertEqual(s.feed("ited] Good news. "), ["Good news."])
        self.assertEqual(s.mood, "excited")

    def test_a_bracket_that_is_not_a_tag_is_spoken(self):
        s = SentenceSplitter()
        self.assertEqual(feed_all(s, ["[not a mood tag] hello."]),
                         ["[not a mood tag] hello."])
        self.assertIsNone(s.mood)

    def test_an_unclosed_bracket_is_released_rather_than_held(self):
        s = SentenceSplitter()
        text = "[" + "x" * 40 + ". "
        self.assertEqual(feed_all(s, [text]), [text.strip()])
        self.assertIsNone(s.mood)

    def test_no_tag_leaves_mood_unset(self):
        s = SentenceSplitter()
        self.assertEqual(feed_all(s, ["Just an answer."]), ["Just an answer."])
        self.assertIsNone(s.mood)

    def test_strip_mood_tag_on_a_finished_reply(self):
        self.assertEqual(strip_mood_tag("[sad] Bad news."), ("sad", "Bad news."))
        self.assertEqual(strip_mood_tag("No tag here."), (None, "No tag here."))
        self.assertEqual(strip_mood_tag(""), (None, ""))

    def test_strip_mood_tag_leaves_a_non_tag_bracket_alone(self):
        self.assertEqual(strip_mood_tag("[see note 1] hello"),
                         (None, "[see note 1] hello"))


class PcmSecondsTests(unittest.TestCase):

    def test_one_second_of_24k_mono_s16(self):
        self.assertAlmostEqual(pcm_seconds(24000 * 2), 1.0)



class FakeVoice:
    """One second of silence per sentence, delivered instantly."""

    def stream_pcm(self, text, previous_text=None):
        yield b"\x00\x00" * 24000


class SpeechStreamAbortTests(unittest.IsolatedAsyncioTestCase):

    async def test_abort_reports_what_has_started_playing(self):
        speech = SpeechStream(FakeVoice())
        speech._buddy = lambda *a, **k: None
        for sentence in ("One.", "Two.", "Three."):
            speech.say(sentence)
        while len(speech._timeline) < 3:
            await asyncio.sleep(0.01)
        # Pretend 1.5 s of audio has played: "Two." is partway through.
        speech._first_chunk_at = time.monotonic() - 1.5
        self.assertEqual(speech.abort(), ["One.", "Two."])

    async def test_abort_before_any_audio_heard_nothing(self):
        speech = SpeechStream(FakeVoice())
        speech._buddy = lambda *a, **k: None
        self.assertEqual(speech.abort(), [])
        speech.say("Too late.")
        await speech._worker
        self.assertEqual(speech._parts, [])


if __name__ == "__main__":
    unittest.main()
