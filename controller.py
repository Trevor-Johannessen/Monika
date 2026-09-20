"""
    The controller is responseible for setting up all required agents and giving an interface for them to be used.
"""

import asyncio
import json
import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import requests

import conversations
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    StreamEvent,
)
from orchestrationAgent import build_orchestrator_options
from prompt import Prompt
from speech import SentenceSplitter, strip_mood_tag

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

# How this turn's words reach the user. The client is persistent and the system
# prompt is fixed for the whole session, but delivery changes per request, so
# the mode rides along with the prompt instead. It also keeps the cached prefix
# intact, which a per-turn system prompt would not.
DELIVERY_STREAMED = (
    "\n\nDelivery: your words are spoken aloud in the room as you write them, "
    "sentence by sentence, while you are still working."
)

DELIVERY_WHOLE = (
    "\n\nDelivery: only your finished reply is spoken, as one clip at the end. "
    "Anything you write before then is discarded unheard, so write no lead-in "
    "and put everything the user needs in the final answer."
)

DELIVERY_SILENT = (
    "\n\nDelivery: this turn is written, not spoken. Nothing is said aloud."
)

ESCALATION_PROMPT = (
    "Continue. Give the user's last message a complete, careful answer now, "
    "using the extra reasoning you have here."
)


class Controller:

    def __init__(self, settings, voice):
        self.settings = settings
        self.session_id: str | None = None
        self.last_update = datetime.now()
        # Whether the reply to the turn in flight will be spoken. The say tool
        # reads this so text-mode callers never make noise in the room.
        self._spoken = False
        # The turn in flight, when it is being spoken as it is written. The say
        # tool writes into this instead of synthesising a clip of its own.
        self._speech = None
        self.history: list[dict] = []  # display-only, for webhooks
        self.initial_prompt = settings.get("inital_prompt", "")
        self.webhooks = settings.get("webhooks", [])
        self._escalate = False
        self.escalation_model = settings.get("escalation_model", "claude-sonnet-5")
        self.default_model = settings.get("default_model", "claude-haiku-4-5-20251001")
        self._base_options: ClaudeAgentOptions = build_orchestrator_options(
            settings, self.clear_session, voice, lambda: self._spoken,
            self._request_escalation, lambda: self._speech,
        )
        # One long-lived CLI for the whole conversation, instead of a fresh
        # process per prompt. Guarded by a lock because two concurrent prompts
        # would otherwise interleave on the same session.
        self._client: ClaudeSDKClient | None = None
        self._drop_client = False
        self._cleared = False
        self._lock = asyncio.Lock()
        self._restore_session()

    def _request_escalation(self):
        self._escalate = True

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
        # Called from the clear_context tool mid-turn, so the client can only
        # be torn down once the turn that asked for it has finished.
        self.session_id = None
        self.history = []
        self._drop_client = True
        self._cleared = True
        self._save_session()

    async def _disconnect(self):
        client, self._client = self._client, None
        self._drop_client = False
        if client is None:
            return
        try:
            await client.disconnect()
        except Exception:
            if self.settings.get("verbose"):
                print("Could not disconnect the agent cleanly")

    async def _ensure_client(self) -> ClaudeSDKClient:
        if self._client is not None:
            return self._client
        opts = self._base_options
        if self.session_id:
            opts = replace(opts, resume=self.session_id)
        client = ClaudeSDKClient(options=opts)
        await client.connect()
        self._client = client
        return client

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

    async def prompt(self, prompt: Prompt, speech=None) -> str:
        """Run one turn. Only one at a time: they share a single CLI session."""
        async with self._lock:
            return await self._run_turn(prompt, speech)

    async def _consume(self, client, splitter, speech) -> tuple[str, bool]:
        """Drain one response, speaking text as it arrives. -> (result, saw_result)"""
        result = ""
        saw_result = False
        async for msg in client.receive_response():
            if speech is not None and isinstance(msg, StreamEvent):
                # Subagent output is not part of the reply to the room.
                if msg.parent_tool_use_id is None:
                    self._feed_speech(msg.event, splitter, speech)
                continue
            if isinstance(msg, ResultMessage):
                saw_result = True
                self.session_id = msg.session_id
                if msg.subtype == "success" and msg.result:
                    result = msg.result
        return result, saw_result

    def _feed_speech(self, event: dict, splitter: SentenceSplitter, speech) -> None:
        kind = event.get("type")
        if kind == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta":
                for sentence in splitter.feed(delta.get("text", "")):
                    speech.mood = speech.mood or splitter.mood
                    speech.say(sentence)
        elif kind == "content_block_stop":
            for sentence in splitter.flush():
                speech.mood = speech.mood or splitter.mood
                speech.say(sentence)

    async def _run_turn(self, prompt: Prompt, speech) -> str:
        self._check_inactivity()
        if self._drop_client:
            await self._disconnect()
        # Whatever was cleared before this turn is already settled; only a
        # clear that happens during it should reach the finally below.
        self._cleared = False

        base_text = self._build_prompt_text(prompt)
        self.history.append({"role": "user", "content": base_text})
        self.update_webhook()

        send_text = base_text
        self._spoken = prompt.return_type == "audio"
        if self._spoken:
            send_text = base_text + VOICE_INSTRUCTION
            send_text += DELIVERY_STREAMED if speech is not None else DELIVERY_WHOLE
        else:
            send_text += DELIVERY_SILENT
        if self._client is None and not self.session_id and self.initial_prompt:
            send_text = f"{self.initial_prompt}\n\n{send_text}"

        self._speech = speech
        splitter = SentenceSplitter()
        time_start = datetime.now()
        result = ""
        self._escalate = False
        try:
            client = await self._ensure_client()
            await client.query(send_text)
            result, _ = await self._consume(client, splitter, speech)

            if self._escalate:
                self._escalate = False
                # Same session, stronger model, no second process: swap the
                # model on the live client and swap it back afterwards.
                await client.set_model(self.escalation_model)
                try:
                    await client.query(ESCALATION_PROMPT)
                    escalated, saw_result = await self._consume(
                        client, SentenceSplitter(), speech
                    )
                    if saw_result and escalated:
                        result = escalated
                finally:
                    try:
                        await client.set_model(self.default_model)
                    except Exception:
                        # Swapping back failed, so the client is gone; let the
                        # handler below report the real failure and drop it.
                        pass
        except BaseException:
            # A CLI that has fallen over would otherwise poison every later
            # turn; the old process-per-prompt healed itself by dying. Keep the
            # session id so the replacement resumes where this left off.
            self._drop_client = True
            raise
        finally:
            self._speech = None
            if self._cleared:
                # clear_context fired during this turn. The id the turn just
                # reported belongs to the session being thrown away, so drop
                # it again -- otherwise the next turn resumes what was cleared.
                self.session_id = None
                self._cleared = False
            if self._drop_client:
                await self._disconnect()
        time_delta = datetime.now() - time_start

        _, result = strip_mood_tag(result)
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
