import asyncio
import os
import re
import socket
import sys
from datetime import datetime

import requests

sys.path.insert(0, "/usr/local/lib/homelab")
from sudolib import request_approval

from claude_agent_sdk import (
    ClaudeAgentOptions,
    HookMatcher,
    create_sdk_mcp_server,
    tool,
)

# A prompt to Monika from inside one of her own turns waits for that turn to
# end, and the turn waits for the command: a deadlock. On 2026-10-04 she ran
# `curl localhost:3333/prompt` to "test herself" and hung for two minutes.
# Her /prompt on either port, under any host name, or her `monika` CLI.
SELF_PROMPT = re.compile(r":333[34]/prompt\b|(?:^|[;&|(]\s*)(?:[\w./~-]*/)?monika(?:\s|$)")


async def block_self_prompt(input_data, tool_use_id, context):
    command = (input_data.get("tool_input") or {}).get("command", "")
    if not SELF_PROMPT.search(command):
        return {}
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            "That sends a prompt to you, Monika, while you are in the middle of a "
            "turn; it would wait for this turn to finish and never return. You are "
            "already running and reachable. Answer the user directly instead."),
    }}


# Deployed next to the service by `make install`, on local disk: the bundled
# copy sits on the fs1 NFS mount and costs ~2.5 s to page in when it is cold.
DEPLOYED_CLI = "/usr/local/bin/monika/claude"

BASE_INSTRUCTIONS = """
You are an chatbot and assistant. Your job is to converse with the user, and use the given tools to execute any request. Be short and to the point: default to a single short sentence, and only go to two or three when the subject genuinely requires it. No preamble, no hedging, no restating the question, no summarizing what you just did. When you do need to report back after doing something, name the outcome or topic only -- "your morning's sorted", not "I checked the calendar, pulled the weather, and turned on the lights" -- never list the individual steps or components you touched. Do not ackowledge any provided extraneous information. If you require information that has not been provided, use any skills to check if that information has been stored elsewhere. You have a personal directory at /etc/monika/files that you can store files at.

You remember your past conversations with the user. The current session is only your short-term memory; every exchange you have ever had is searchable through the recall skill. Whenever the user refers to something from before, asks what was said or decided, or mentions a name or detail you have no context for in this session, search your memory with the recall skill before answering. Never tell the user you cannot remember earlier conversations, and never say you have no memory between sessions -- you do. Recall silently and answer as though you simply remembered.

Every prompt is followed by a JSON object of context attributes from the client. It is context only: use what is relevant and never read it back to the user. When it contains "led": true, the room's LED strip is available for this request and you should use the led-strip skill to show what you are reporting — most often the matching weather scene when you report conditions. The lights are incidental to your answer: never mention them, never say whether they worked, and never let them delay or change what you say. When that attribute is absent or false, leave the strip alone.

When the attributes contain "source": "discord", the user is typing to you on Discord and your reply is shown as a Discord message. Discord renders Markdown, so formatting is fine there. Keep the reply under about 1800 characters; anything longer, or a table or file the user asked for, goes in a file you write under ~/.monika/outbox/, with its full path on a line of its own in your reply -- that line is removed and the file is sent as an attachment. A "thread" attribute names the Discord thread the message was posted in; one thread is one topic, but they all share this one conversation. When the attributes contain "files", those are files the user uploaded, already saved on disk at those paths; images, PDFs and text files are also attached to the message itself, and for anything else (CSV, zip, logs, code) use Bash on the path.

How your reply reaches the user changes from turn to turn, and every prompt ends with a Delivery line telling you which it is this time. When it says your words are spoken as you write them, then before a job that needs tools or will take a moment, write one short plain sentence naming the general topic -- never the individual steps or components -- then do the work, then write the answer, and do not repeat that lead-in in the answer because the user has already heard it. When it says only your finished reply is spoken, write no lead-in at all: nothing you write before the end is ever heard, so the final answer has to carry everything on its own. When it says the turn is written and not spoken, just answer. Never use markdown, lists, headings or symbols in a reply that will be spoken: write the words you want said. The `say` tool is only for a sentence that has to be spoken from inside a long run of tool calls, where you cannot write ordinary text; it always speaks in the room, and it is a tool, never a skill.

You may begin a reply with a single mood tag in square brackets -- one of alert, excited, happy, music, neutral, sad, sleepy, thinking, weather -- and the matching sprite goes up on the room monitor by itself. It is stripped before anything is spoken or shown. Use the one that fits the topic or tone, leave it off when none does, and never mention it or run the buddy command yourself.

You start every reply on a fast, lightweight model, which is the right call for almost everything you get asked. If a request genuinely needs more than that -- real multi-step reasoning, a tricky piece of code, something you are not confident you can answer well quickly -- first write one short sentence telling the user this needs more thought and you are switching to a smarter model, then call the escalate_to_sonnet tool and stop there; do not try to answer yourself. A stronger model will pick the reply up from where you left off. Do not escalate for ordinary conversation or anything you can already answer well.

Anything that will take more than a few seconds of work -- research, a multi-step job, anything you would otherwise hand to the Task tool -- goes to start_background_task instead, so the user can keep talking to you while it runs. Give it a short description and a complete, self-contained prompt (the worker sees nothing of this conversation), say in one short sentence that you are on it, and end your turn; do not wait for it. When it finishes, its result arrives as a message starting "[Background task finished"; tell the user the outcome then. Quick lookups that take a single tool call stay in the foreground.

Never send a prompt to yourself: no request to your own /prompt endpoint (port 3333 or 3334, on any host) and no running the `monika` command. You are already running, so it would only wait on the turn you are in. If the user asks whether you can hear them or whether something is working, answer them directly.
""".strip()

BACKGROUND_INSTRUCTIONS = """
You are a background worker for Monika, a home assistant. Nobody is watching you work and nobody can answer questions, so make reasonable assumptions and finish the job. When you are done, reply with a short plain-text summary of the outcome -- the facts Monika needs to tell the user, without markdown -- and nothing else.
""".strip()


def build_background_options(settings):
    """Options for a background worker: Monika's tools, a session of its own."""
    return ClaudeAgentOptions(
        system_prompt=BACKGROUND_INSTRUCTIONS,
        allowed_tools=["Bash", "WebSearch"],
        permission_mode="bypassPermissions",
        skills="all",
        model=settings.get("default_model", "claude-haiku-5-5"),
        thinking={"type": "disabled"},
        **({"cli_path": DEPLOYED_CLI} if os.path.isfile(DEPLOYED_CLI) else {}),
    )


def build_orchestrator_options(settings, on_clear, voice, is_spoken, on_escalate, get_speech,
                               on_background, get_origin):
    """Build the ClaudeAgentOptions for the orchestrator.

    on_clear: callable invoked by the clear_context tool to reset the conversation session.
    voice: the Voice instance server.py already built, used by the say tool.
    is_spoken: callable returning True when this turn's reply will be spoken aloud.
    on_escalate: callable invoked by the escalate_to_sonnet tool to ask the
        controller to redo this turn on a stronger model.
    get_speech: callable returning the turn's SpeechStream, or None when this
        turn is not being spoken as it is written.
    on_background: callable(description, prompt) that starts a background
        worker and reports its result back into the conversation later.
    get_origin: callable returning (source, reply_to) for the current turn, as
        the client sent them in its attributes.
    """
    model = settings.get("default_model", "claude-haiku-5-5")
    speaker_url = settings.get("speaker_server", "http://pi1:3335")

    @tool("clear_context", "Clears the conversation history. Use this when the user asks to reset, clear, or start a new conversation.", {})
    async def clear_context(args):
        on_clear()
        return {"content": [{"type": "text", "text": "Conversation context has been cleared."}]}

    @tool("say", "Speak one short sentence aloud to the user now, from inside a long run of tool calls where you cannot write ordinary text. This is a tool, not a skill. Ordinary text you write is already spoken as you write it -- do not use this for that.", {"text": str})
    async def say(args):
        # Text-mode callers (the monika CLI, the dashboard, scheduleTask) must not
        # blast audio into the room, so the turn has to have asked for audio.
        if not is_spoken():
            return {"content": [{"type": "text", "text": "This turn is not spoken; nothing was said."}]}
        # A streaming turn already has one ordered PCM stream going to the
        # speaker; joining it keeps this sentence in sequence and costs no TTS
        # round trip inside the tool call.
        speech = get_speech()
        if speech is not None:
            speech.say(args["text"])
            return {"content": [{"type": "text", "text": "Spoken."}]}
        try:
            # generate_voice does a blocking ElevenLabs call, a file write and an
            # os.fork(); requests.post blocks too. Neither may run on the event loop.
            audio = await asyncio.to_thread(voice.generate_voice, args["text"])
            await asyncio.to_thread(
                requests.post,
                f"{speaker_url}/play",
                # role=voice is what ducks the music underneath; X-Client-Name is
                # the opt-in header the speaker server uses to name us on its
                # dashboard instead of showing a bare IP.
                files={"file": ("say.mp3", audio, "audio/mpeg")},
                data={"role": "voice"},
                headers={"X-Client-Name": "monika"},
                timeout=30,
            )
        except Exception as exc:
            return {"content": [{"type": "text", "text": f"Could not speak: {exc}"}], "is_error": True}
        return {"content": [{"type": "text", "text": "Spoken."}]}

    @tool("escalate_to_sonnet", "Ask a stronger model to take over and finish this reply, because it needs more careful reasoning than you can give quickly. Announce this to the user with the say tool first, then call this and stop -- do not answer yourself.", {})
    async def escalate_to_sonnet(args):
        on_escalate()
        return {"content": [{"type": "text", "text": "Escalating to a stronger model now. Stop here -- do not continue answering."}]}

    @tool("start_background_task", "Start a job that runs in the background while you keep talking to the user. The worker has your Bash, WebSearch and skills but sees none of this conversation, so the prompt must be complete on its own. Its result comes back to you as a later message. After calling this, tell the user you are on it and end your turn.", {"description": str, "prompt": str})
    async def start_background_task(args):
        on_background(args["description"], args["prompt"])
        return {"content": [{"type": "text", "text": "Started. You will be told when it finishes -- end your turn now."}]}

    @tool("request_sudo_approval", "Request approval to run a sudo command on this machine. Provide the command (without sudo), what you were doing, why you need it, and potential risks. The request will be added to a pending approval queue that the user reviews; you are told the outcome in a later message. Do not proceed without approval.", {"command": str, "context": str, "purpose": str, "risks": str})
    async def request_sudo_approval(args):
        # The queue approve.py reads; approve.py tells this session the outcome,
        # and posts it to the Discord thread when the request came from there.
        source, reply_to = get_origin()
        queued = request_approval(
            source="discord" if (source or "").startswith("discord") else "monika",
            # Monika has one session, so this only has to tell requests apart in the queue.
            session_id=f"monika-{datetime.now():%Y%m%d-%H%M%S}-{os.urandom(2).hex()}",
            command=args["command"],
            context=args["context"],
            purpose=args["purpose"],
            risks=args["risks"],
            host=socket.gethostname().split(".")[0],
            reply_to=str(reply_to or ""),
        )
        if not queued:
            return {"content": [{"type": "text", "text": "Error adding approval request to the queue."}], "is_error": True}
        return {"content": [{"type": "text", "text": f"Sudo approval request added to pending queue. Command: {args['command']}. Waiting for user approval to proceed."}]}

    control_server = create_sdk_mcp_server(
        name="control",
        version="1.0.0",
        tools=[clear_context, say, escalate_to_sonnet, start_background_task, request_sudo_approval],
    )

    return ClaudeAgentOptions(
        system_prompt=BASE_INSTRUCTIONS,
        mcp_servers={"control": control_server},
        allowed_tools=[
            "Bash",
            "WebSearch",
            "Task",
            "mcp__control__clear_context",
            "mcp__control__say",
            "mcp__control__escalate_to_sonnet",
            "mcp__control__start_background_task",
            "mcp__control__request_sudo_approval",
        ],
        permission_mode="bypassPermissions",
        hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[block_self_prompt])]},
        # Skills live in ~/.claude/skills; "all" is what enables the Skill tool
        # and points the CLI at them. The led-strip skill is how the lights are driven.
        skills="all",
        model=model,
        # Haiku 4.5 has no thinking-effort dial, and a thinking block costs
        # 2-3 s on a model that answers in 0.2 s without one.
        thinking={"type": "disabled"},
        # Text deltas, so a sentence can be spoken before the turn finishes.
        include_partial_messages=True,
        **({"cli_path": DEPLOYED_CLI} if os.path.isfile(DEPLOYED_CLI) else {}),
    )
