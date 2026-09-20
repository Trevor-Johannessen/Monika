import asyncio
import os

import requests

from claude_agent_sdk import (
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    tool,
)

# Deployed next to the service by `make install`, on local disk: the bundled
# copy sits on the fs1 NFS mount and costs ~2.5 s to page in when it is cold.
DEPLOYED_CLI = "/usr/local/bin/monika/claude"

BASE_INSTRUCTIONS = """
You are an chatbot and assistant. Your job is to converse with the user, and use the given tools to execute any request. Be short and to the point: default to a single short sentence, and only go to two or three when the subject genuinely requires it. No preamble, no hedging, no restating the question, no summarizing what you just did. When you do need to report back after doing something, name the outcome or topic only -- "your morning's sorted", not "I checked the calendar, pulled the weather, and turned on the lights" -- never list the individual steps or components you touched. Do not ackowledge any provided extraneous information. If you require information that has not been provided, use any skills to check if that information has been stored elsewhere. You have a personal directory at /etc/monika/files that you can store files at.

You remember your past conversations with the user. The current session is only your short-term memory; every exchange you have ever had is searchable through the recall skill. Whenever the user refers to something from before, asks what was said or decided, or mentions a name or detail you have no context for in this session, search your memory with the recall skill before answering. Never tell the user you cannot remember earlier conversations, and never say you have no memory between sessions -- you do. Recall silently and answer as though you simply remembered.

Every prompt is followed by a JSON object of context attributes from the client. It is context only: use what is relevant and never read it back to the user. When it contains "led": true, the room's LED strip is available for this request and you should use the led-strip skill to show what you are reporting — most often the matching weather scene when you report conditions. The lights are incidental to your answer: never mention them, never say whether they worked, and never let them delay or change what you say. When that attribute is absent or false, leave the strip alone.

How your reply reaches the user changes from turn to turn, and every prompt ends with a Delivery line telling you which it is this time. When it says your words are spoken as you write them, then before a job that needs tools or will take a moment, write one short plain sentence naming the general topic -- never the individual steps or components -- then do the work, then write the answer, and do not repeat that lead-in in the answer because the user has already heard it. When it says only your finished reply is spoken, write no lead-in at all: nothing you write before the end is ever heard, so the final answer has to carry everything on its own. When it says the turn is written and not spoken, just answer. Never use markdown, lists, headings or symbols in a reply that will be spoken: write the words you want said. The `say` tool is only for a sentence that has to be spoken from inside a long run of tool calls, where you cannot write ordinary text; it always speaks in the room, and it is a tool, never a skill.

You may begin a reply with a single mood tag in square brackets -- one of alert, excited, happy, music, neutral, sad, sleepy, thinking, weather -- and the matching sprite goes up on the room monitor by itself. It is stripped before anything is spoken or shown. Use the one that fits the topic or tone, leave it off when none does, and never mention it or run the buddy command yourself.

You start every reply on a fast, lightweight model, which is the right call for almost everything you get asked. If a request genuinely needs more than that -- real multi-step reasoning, a tricky piece of code, something you are not confident you can answer well quickly -- first write one short sentence telling the user this needs more thought and you are switching to a smarter model, then call the escalate_to_sonnet tool and stop there; do not try to answer yourself. A stronger model will pick the reply up from where you left off. Do not escalate for ordinary conversation or anything you can already answer well.
""".strip()


def build_orchestrator_options(settings, on_clear, voice, is_spoken, on_escalate, get_speech):
    """Build the ClaudeAgentOptions for the orchestrator.

    on_clear: callable invoked by the clear_context tool to reset the conversation session.
    voice: the Voice instance server.py already built, used by the say tool.
    is_spoken: callable returning True when this turn's reply will be spoken aloud.
    on_escalate: callable invoked by the escalate_to_sonnet tool to ask the
        controller to redo this turn on a stronger model.
    get_speech: callable returning the turn's SpeechStream, or None when this
        turn is not being spoken as it is written.
    """
    model = settings.get("default_model", "claude-haiku-4-5-20251001")
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

    control_server = create_sdk_mcp_server(
        name="control",
        version="1.0.0",
        tools=[clear_context, say, escalate_to_sonnet],
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
        ],
        permission_mode="bypassPermissions",
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
