"""request_sudo_approval queues the host it was given, or the local machine when omitted."""

import asyncio
import os
import socket
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import orchestrationAgent
from mcp.types import CallToolRequest, CallToolRequestParams, ListToolsRequest


def control_server():
    """Build the orchestrator's control server with request_approval replaced by a recorder."""
    options = orchestrationAgent.build_orchestrator_options(
        {}, on_clear=lambda: None, voice=None, is_spoken=lambda: False,
        on_escalate=lambda: None, get_speech=lambda: None,
        on_background=lambda d, p: None, get_origin=lambda: ("", None),
    )
    return options.mcp_servers["control"]["instance"]


def call(server, arguments):
    request = CallToolRequest(method="tools/call", params=CallToolRequestParams(
        name="request_sudo_approval", arguments=arguments))
    result = asyncio.run(server.request_handlers[CallToolRequest](request)).root
    return result


BASE = {"command": "systemctl restart vanilla", "context": "Restarting the game server",
        "purpose": "Needs root", "risks": "Players get disconnected"}


class RequestSudoApprovalTests(unittest.TestCase):

    def setUp(self):
        self.server = control_server()
        patcher = mock.patch.object(orchestrationAgent, "request_approval", return_value=True)
        self.request_approval = patcher.start()
        self.addCleanup(patcher.stop)

    def test_host_is_optional_in_schema(self):
        tools = asyncio.run(self.server.request_handlers[ListToolsRequest](
            ListToolsRequest(method="tools/list"))).root.tools
        schema = next(t for t in tools if t.name == "request_sudo_approval").inputSchema
        self.assertIn("host", schema["properties"])
        self.assertEqual(sorted(schema["required"]), ["command", "context", "purpose", "risks"])

    def test_host_passed_is_queued(self):
        result = call(self.server, dict(BASE, host="minecraft2"))
        self.assertFalse(result.isError)
        self.assertEqual(self.request_approval.call_args.kwargs["host"], "minecraft2")
        self.assertEqual(self.request_approval.call_args.kwargs["command"], BASE["command"])

    def test_omitted_host_is_queued_as_local(self):
        result = call(self.server, dict(BASE))
        self.assertFalse(result.isError)
        self.assertEqual(self.request_approval.call_args.kwargs["host"],
                         socket.gethostname().split(".")[0])

    def test_invalid_host_is_rejected(self):
        result = call(self.server, dict(BASE, host="deploy1; rm -rf ~"))
        self.assertTrue(result.isError)
        self.request_approval.assert_not_called()


if __name__ == "__main__":
    unittest.main()
