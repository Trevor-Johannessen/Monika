"""Attachments on /prompt, and background results reaching a notify URL.

The SDK client is a stand-in: these check what the controller sends it and
what it does with the answer, not the model.
"""

import asyncio
import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import controller as controller_mod
from claude_agent_sdk import ResultMessage
from prompt import Prompt

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()


def result(text):
    return ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1,
                         is_error=False, num_turns=1, session_id="s1", result=text)


class FakeClient:
    def __init__(self, answer="ok"):
        self.answer = answer
        self.sent = []

    async def query(self, prompt):
        if isinstance(prompt, str):
            self.sent.append(prompt)
        else:
            self.sent.append([m async for m in prompt])

    async def receive_response(self):
        yield result(self.answer)


class ControllerTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.patches = [
            mock.patch.object(controller_mod, "STATE_PATH", tmp / "state.json"),
            mock.patch.object(controller_mod, "REMINDERS_DIR", str(tmp / "none")),
            mock.patch.dict(os.environ, {"MONIKA_CONVERSATIONS_DIR": str(tmp / "conv")}),
        ]
        for p in self.patches:
            p.start()
        self.settings = {"notify_urls": {"discord": "http://notify.test/notify"}}
        self.c = controller_mod.Controller(self.settings, voice=None)
        self.client = FakeClient()
        self.c._client = self.client

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def logged(self):
        files = list(Path(os.environ["MONIKA_CONVERSATIONS_DIR"]).glob("*.jsonl"))
        return [json.loads(line) for f in files for line in f.read_text().splitlines()]


class AttachmentTurnTests(ControllerTestCase):

    def test_plain_text_is_sent_as_a_string(self):
        asyncio.run(self.c.prompt(Prompt(prompt="hi")))
        self.assertIsInstance(self.client.sent[0], str)

    def test_attachments_ride_on_one_user_message(self):
        asyncio.run(self.c.prompt(Prompt(
            prompt="what is this",
            attachments=[{"name": "a.png", "media_type": "image/png", "data": PNG}],
        )))
        [msg] = self.client.sent[0]
        content = msg["message"]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertIn("what is this", content[0]["text"])
        self.assertEqual(content[1]["type"], "image")
        self.assertEqual(content[1]["source"]["media_type"], "image/png")

    def test_conversation_log_names_the_files(self):
        asyncio.run(self.c.prompt(Prompt(
            prompt="read this",
            attachments=[{"name": "n.txt", "media_type": "text/plain",
                          "data": base64.b64encode(b"hello").decode()}],
        )))
        self.assertEqual(self.logged()[0]["user"], "read this\n[attached: n.txt]")

    def test_a_rejected_attachment_is_the_reply_and_no_model_call(self):
        reply = asyncio.run(self.c.prompt(Prompt(
            prompt="x",
            attachments=[{"name": "b.bin", "media_type": "application/octet-stream",
                          "data": base64.b64encode(b"\xff\xfe\x00").decode()}],
        )))
        self.assertIn("unsupported file type", reply)
        self.assertEqual(self.client.sent, [])


class BackgroundNotifyTests(ControllerTestCase):

    def run_background(self, source, reply_to=None, spoken=False):
        async def no_worker(prompt, options):
            yield result("worker output")

        posts = []
        with mock.patch.object(controller_mod, "query", no_worker), \
             mock.patch.object(controller_mod.requests, "post",
                               lambda url, **kw: posts.append((url, kw["json"]))), \
             mock.patch.object(self.c, "_announce", mock.AsyncMock()) as announce:
            self.client.answer = "it is done"
            asyncio.run(self.c._run_background("job", "do it", spoken, source, reply_to))
        return posts, announce

    def test_a_discord_job_posts_its_answer_back_to_the_thread(self):
        posts, announce = self.run_background("discord", reply_to=123)
        self.assertEqual(posts, [("http://notify.test/notify",
                                  {"text": "it is done", "reply_to": 123})])
        announce.assert_not_called()
        self.assertIn("'source': 'discord'", self.client.sent[0])

    def test_a_spoken_discord_job_still_goes_to_discord_not_the_room(self):
        posts, announce = self.run_background("discord", spoken=True)
        self.assertEqual(len(posts), 1)
        announce.assert_not_called()

    def test_a_room_job_is_announced_and_posts_nothing(self):
        posts, announce = self.run_background(None, spoken=True)
        self.assertEqual(posts, [])
        announce.assert_awaited_once_with("it is done")

    def test_the_turn_records_where_it_came_from(self):
        asyncio.run(self.c.prompt(Prompt(
            prompt="hi", attributes={"source": "discord", "reply_to": 42})))
        self.assertEqual((self.c._source, self.c._reply_to), ("discord", 42))


if __name__ == "__main__":
    unittest.main()
