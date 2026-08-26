"""
    The controller is responseible for setting up all required agents and giving an interface for them to be used.
"""

import json
import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import requests

import conversations
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from orchestrationAgent import build_orchestrator_options
from prompt import Prompt

REMINDERS_DIR = "/etc/monika/reminders"
INACTIVITY_SECONDS = 900

# Survives a restart so a redeploy mid-conversation doesn't drop the thread.
# Lives on the NFS home mount next to the conversation log.
STATE_PATH = Path.home() / ".monika" / "state.json"

VOICE_INSTRUCTION = (
    "\n\nIMPORTANT: Respond using complete words only. Do not use any special characters "
    "such as &, *, #, @, or degree symbols. Write out all units and measurements as words "
    '(e.g. "degrees" not "°", "and" not "&", "percent" not "%").'
)


class Controller:

    def __init__(self, settings):
        self.settings = settings
        self.session_id: str | None = None
        self.last_update = datetime.now()
        self.history: list[dict] = []  # display-only, for webhooks
        self.initial_prompt = settings.get("inital_prompt", "")
        self.webhooks = settings.get("webhooks", [])
        self._base_options: ClaudeAgentOptions = build_orchestrator_options(settings, self.clear_session)
        self._restore_session()

    def _restore_session(self):
        """Pick the live session back up after a restart, if it is still fresh.

        The SDK's session transcripts outlive the process, so the only thing
        lost on restart is the session id. Anything older than the inactivity
        window would have been dropped anyway; long-term recall is the `recall`
        skill's job, not this one's.
        """
        try:
            state = json.loads(STATE_PATH.read_text())
            last = datetime.strptime(state["last_update"], "%Y-%m-%dT%H:%M:%S")
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return
        if (datetime.now() - last).total_seconds() > INACTIVITY_SECONDS:
            return
        self.session_id = state.get("session_id")
        self.last_update = last
        if self.settings.get("verbose") and self.session_id:
            print(f"Resuming session {self.session_id} from {last}")

    def _save_session(self):
        try:
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(json.dumps({
                "session_id": self.session_id,
                "last_update": self.last_update.strftime("%Y-%m-%dT%H:%M:%S"),
            }))
        except OSError:
            pass

    def clear_session(self):
        self.session_id = None
        self.history = []
        self._save_session()

    def _check_inactivity(self):
        if (datetime.now() - self.last_update).total_seconds() > INACTIVITY_SECONDS:
            self.clear_session()

    def update_webhook(self):
        payload = self.to_dict()
        for url in self.webhooks:
            try:
                requests.post(url, json=payload)
            except Exception:
                if self.settings.get("verbose"):
                    print(f"Could not update {url}")

    def to_dict(self):
        return {
            "last_updated": self.last_update.strftime("%Y-%m-%d %H:%M:%S"),
            "history": self.history,
        }

    def _load_pending_reminders(self) -> str:
        if not os.path.isdir(REMINDERS_DIR):
            return ""
        blocks = []
        for name in sorted(os.listdir(REMINDERS_DIR)):
            path = os.path.join(REMINDERS_DIR, name)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r") as f:
                    body = f.read().strip()
            except OSError:
                continue
            blocks.append(f"File: {name}\n{body}")
        return "\n\n".join(blocks)

    def _build_prompt_text(self, prompt: Prompt) -> str:
        prompt.attributes["time"] = prompt.attributes.get(
            "time", datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
        )
        text = (
            f"{prompt.prompt}\n\nBelow is information that may help with the above prompt. "
            f"Only use relevant information:\n{prompt.attributes}"
        )
        reminders_text = self._load_pending_reminders()
        if reminders_text:
            text += (
                "\n\nPending reminders (evaluate each Trigger against the current time and the user's "
                "message; if fired, surface the message to the user and delete the file; otherwise "
                "ignore silently):\n" + reminders_text
            )
        return text

    async def prompt(self, prompt: Prompt) -> str:
        self._check_inactivity()

        base_text = self._build_prompt_text(prompt)
        self.history.append({"role": "user", "content": base_text})
        self.update_webhook()

        send_text = base_text
        if prompt.return_type == "audio":
            send_text = base_text + VOICE_INSTRUCTION

        opts = self._base_options
        if self.session_id:
            opts = replace(opts, resume=self.session_id)
        elif self.initial_prompt:
            send_text = f"{self.initial_prompt}\n\n{send_text}"

        time_start = datetime.now()
        result = ""
        async for msg in query(prompt=send_text, options=opts):
            if isinstance(msg, ResultMessage):
                self.session_id = msg.session_id
                if msg.subtype == "success" and msg.result:
                    result = msg.result
        time_end = datetime.now()
        time_delta = time_end - time_start

        self.last_update = datetime.now()
        self.history.append({"role": "assistant", "content": result})

        # Long-term memory: the raw prompt, not the context-padded one the model
        # saw. Searched later by the `recall` skill.
        conversations.append(prompt.prompt, result, session=self.session_id,
                             when=self.last_update)
        self._save_session()

        if self.settings.get("verbose"):
            print(f"Response took {time_delta.total_seconds()} seconds.")

        self.update_webhook()
        return result
