"""A runaway turn stops at a step limit, and says so rather than going silent."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import controller as controller_mod
import orchestrationAgent as agent
from claude_agent_sdk import ResultMessage


def result(subtype, text=None):
    return ResultMessage(subtype=subtype, duration_ms=1, duration_api_ms=1, is_error=subtype != "success",
                         num_turns=1, session_id="s", result=text)


class FakeClient:
    def __init__(self, message):
        self.message = message

    async def receive_response(self):
        yield self.message


class TurnLimitTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.controller = controller_mod.Controller.__new__(controller_mod.Controller)

    async def consume(self, message, speech=None):
        return await self.controller._consume(FakeClient(message), None, speech)

    def test_both_kinds_of_turn_are_capped(self):
        args = [mock.MagicMock()] * 7
        self.assertEqual(agent.build_orchestrator_options({}, *args).max_turns, agent.MAX_TURNS)
        self.assertEqual(agent.build_background_options({}).max_turns, agent.BACKGROUND_MAX_TURNS)

    async def test_hitting_the_limit_is_reported(self):
        reply, saw = await self.consume(result("error_max_turns"))
        self.assertEqual(reply, controller_mod.TURN_LIMIT_REPLY)
        self.assertTrue(saw)

    async def test_hitting_the_limit_is_spoken_on_a_spoken_turn(self):
        speech = mock.MagicMock()
        await self.consume(result("error_max_turns"), speech)
        speech.say.assert_called_once_with(controller_mod.TURN_LIMIT_REPLY)

    async def test_other_failures_are_unchanged(self):
        self.assertEqual((await self.consume(result("error_during_execution")))[0], "")
        self.assertEqual((await self.consume(result("success", "hi")))[0], "hi")


if __name__ == "__main__":
    unittest.main()
