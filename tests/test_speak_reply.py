"""POST /prompt with speak set: text comes back at once and the speaker gets it too."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

stubs = {name: mock.MagicMock() for name in ("controller", "voice", "voice_elevenlabs", "dashboard", "speech")}
with mock.patch.dict(sys.modules, stubs):
    import server
from prompt import Prompt


class SpeakReplyTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.controller = mock.MagicMock()
        self.controller.prompt = mock.AsyncMock(return_value="hello there")
        self.controller._announce = mock.AsyncMock()
        patcher = mock.patch.object(server, "controller", self.controller)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def ask(self, **fields):
        reply = await server.prompt(Prompt(prompt="hi", **fields))
        await asyncio.sleep(0)  # let the background task run
        return reply

    async def test_silent_by_default(self):
        self.assertEqual(await self.ask(), {"message": "hello there"})
        self.controller._announce.assert_not_called()

    async def test_speak_returns_text_and_announces(self):
        self.assertEqual(await self.ask(speak=True), {"message": "hello there"})
        self.controller._announce.assert_awaited_once_with("hello there")

    async def test_speaker_failure_keeps_the_text(self):
        self.controller._announce.side_effect = RuntimeError("speaker down")
        self.assertEqual(await self.ask(speak=True), {"message": "hello there"})

    async def test_blank_reply_stays_silent(self):
        self.controller.prompt.return_value = "  "
        await self.ask(speak=True)
        self.controller._announce.assert_not_called()


if __name__ == "__main__":
    unittest.main()
