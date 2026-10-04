"""Monika must never send a prompt to herself mid-turn: it deadlocks."""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrationAgent import block_self_prompt


def decision(command):
    out = asyncio.run(block_self_prompt({"tool_input": {"command": command}}, "t1", None))
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision")


class SelfPromptGuardTests(unittest.TestCase):

    def test_blocked(self):
        for command in (
            'curl -s -i http://localhost:3333/prompt -X POST -d \'{"prompt":"test"}\'',
            "curl -X POST http://deploy1:3333/prompt -d @body.json",
            "curl -k https://127.0.0.1:3334/prompt",
            'monika "hello"',
            'cd /tmp && monika "are you there"',
            "/usr/local/bin/monika/monika test",
        ):
            with self.subTest(command=command):
                self.assertEqual(decision(command), "deny")

    def test_allowed(self):
        for command in (
            "ls ~/.monika/outbox",
            "cat /usr/local/bin/monika/settings.json",
            "python3 ~/.claude/skills/scheduler/schedule.py list",
            "curl -s http://localhost:3333/",
            "curl -s http://pi1:3335/play",
            "grep monika notes.txt",
        ):
            with self.subTest(command=command):
                self.assertIsNone(decision(command))


if __name__ == "__main__":
    unittest.main()
