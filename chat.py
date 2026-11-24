"""A small chat page for talking to Monika, meant to be embedded as an iframe
(the Home Assistant dashboard's webpage card). It posts to /prompt on the same
server; the Voice switch has the reply read aloud in the browser itself, using the
MP3 from /chat/speak, rather than on the room speaker.

Every load of the page starts Monika on a fresh session (/chat/new), so opening
the dashboard always begins a new conversation. The dropdown lists earlier
sessions from the conversation log; picking one resumes it (/chat/resume).
"""
import asyncio
from datetime import datetime

import conversations
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monika</title>
<style>
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body { font: 14px/1.4 Roboto, system-ui, sans-serif; color: #212121; background: #fff;
         display: flex; flex-direction: column; }
  header { display: flex; align-items: center; justify-content: space-between;
           padding: 10px 14px; border-bottom: 1px solid #eee; }
  header b { font-size: 15px; }
  header select { flex: 1; min-width: 0; margin: 0 12px; padding: 4px 6px; font: inherit;
                  font-size: 13px; border: 1px solid #ddd; border-radius: 6px; background: #fff; }
  .switch { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #616161;
            cursor: pointer; user-select: none; }
  .switch input { display: none; }
  .track { width: 36px; height: 20px; border-radius: 10px; background: #bdbdbd;
           position: relative; transition: background .2s; }
  .track::after { content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px;
                  border-radius: 50%; background: #fff; transition: left .2s; }
  .switch input:checked + .track { background: #03a9f4; }
  .switch input:checked + .track::after { left: 18px; }
  #log { flex: 1; overflow-y: auto; padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; }
  .msg { max-width: 85%; padding: 8px 12px; border-radius: 14px; white-space: pre-wrap;
         word-wrap: break-word; }
  .user { align-self: flex-end; background: #03a9f4; color: #fff; border-bottom-right-radius: 4px; }
  .bot { align-self: flex-start; background: #f1f1f1; border-bottom-left-radius: 4px; }
  .bot.pending { color: #9e9e9e; font-style: italic; }
  .bot.error { background: #fdecea; color: #c62828; }
  form { display: flex; gap: 8px; padding: 10px 14px; border-top: 1px solid #eee; }
  textarea { flex: 1; resize: none; height: 38px; padding: 8px 12px; border: 1px solid #ddd;
             border-radius: 19px; font: inherit; outline: none; }
  textarea:focus { border-color: #03a9f4; }
  button { border: 0; border-radius: 19px; padding: 0 16px; background: #03a9f4; color: #fff;
           font: inherit; cursor: pointer; }
  button:disabled { background: #bdbdbd; cursor: default; }
</style>
</head>
<body>
<header>
  <b>Monika</b>
  <select id="convs"><option value="">New conversation</option></select>
  <label class="switch">Text
    <input type="checkbox" id="voice"><span class="track"></span>
  Voice</label>
</header>
<div id="log"></div>
<form id="form">
  <textarea id="text" placeholder="Message Monika…" autofocus></textarea>
  <button id="send">Send</button>
</form>
<script>
const log = document.getElementById("log");
const text = document.getElementById("text");
const send = document.getElementById("send");
const voice = document.getElementById("voice");
const convs = document.getElementById("convs");
// One element for all replies: playing it inside the Send click unlocks it, so the
// reply can start later without the browser's autoplay block.
const player = new Audio();
const SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

voice.checked = localStorage.getItem("monika-chat-voice") === "1";
voice.onchange = () => localStorage.setItem("monika-chat-voice", voice.checked ? "1" : "0");

function add(role, content, extra) {
  const div = document.createElement("div");
  div.className = "msg " + role + (extra ? " " + extra : "");
  div.textContent = content;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}
// Opening the page (the dashboard) always starts a fresh conversation.
async function startNew() {
  log.innerHTML = "";
  await fetch("/chat/new", {method: "POST"});
}

async function loadConversations() {
  try {
    const list = await (await fetch("/chat/conversations")).json();
    convs.length = 1;
    for (const c of list) {
      const o = document.createElement("option");
      o.value = c.session;
      o.textContent = c.label;
      convs.appendChild(o);
    }
  } catch (e) {}
}

convs.onchange = async () => {
  if (!convs.value) { await startNew(); return; }
  log.innerHTML = "";
  const pending = add("bot", "Loading…", "pending");
  try {
    const r = await fetch("/chat/resume", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({session: convs.value}),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    pending.remove();
    for (const m of (await r.json()).messages) {
      if (m.user) add("user", m.user);
      if (m.assistant) add("bot", m.assistant);
    }
  } catch (e) {
    pending.className = "msg bot error";
    pending.textContent = "Couldn't resume that conversation (" + e.message + ")";
  }
  text.focus();
};

startNew().then(loadConversations);

async function submit() {
  const prompt = text.value.trim();
  if (!prompt || send.disabled) return;
  text.value = "";
  add("user", prompt);
  const pending = add("bot", "Thinking…", "pending");
  send.disabled = true;
  const speak = voice.checked;
  if (speak) { player.src = SILENCE; player.play().catch(() => {}); }
  try {
    const r = await fetch("/prompt", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({prompt,
                            attributes: {source: "homeassistant-dashboard"}}),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const reply = (await r.json()).message || "";
    pending.className = "msg bot";
    pending.textContent = reply;
    if (speak && reply.trim()) say(reply);
  } catch (e) {
    pending.className = "msg bot error";
    pending.textContent = "Couldn't reach Monika (" + e.message + ")";
  }
  send.disabled = false;
  log.scrollTop = log.scrollHeight;
  text.focus();
}

async function say(reply) {
  try {
    const r = await fetch("/chat/speak", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text: reply}),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    URL.revokeObjectURL(player.src);
    player.src = URL.createObjectURL(await r.blob());
    await player.play();
  } catch (e) {
    add("bot", "Couldn't play the reply (" + e.message + ")", "error");
  }
}

document.getElementById("form").onsubmit = e => { e.preventDefault(); submit(); };
text.onkeydown = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } };
</script>
</body>
</html>
"""


class _Speak(BaseModel):
    text: str


class _Resume(BaseModel):
    session: str


def _label(entries: list[dict]) -> str:
    when = datetime.strptime(entries[-1]["ts"], "%Y-%m-%dT%H:%M:%S")
    first = " ".join(entries[0].get("user", "").split())
    if len(first) > 50:
        first = first[:50] + "…"
    return f"{when:%b %d, %-I:%M %p} · {first}"


def register(app: FastAPI, voice, controller) -> None:
    @app.get("/chat", response_class=HTMLResponse)
    async def chat_page():
        return HTMLResponse(_HTML)

    @app.post("/chat/new")
    async def chat_new():
        await controller.switch_session(None)
        return {"ok": True}

    @app.get("/chat/conversations")
    async def chat_conversations():
        """Newest first; only sessions recent enough to still be resumable."""
        grouped = conversations.sessions()
        return [{"session": sid, "label": _label(entries)}
                for sid, entries in reversed(list(grouped.items()))][:30]

    @app.post("/chat/resume")
    async def chat_resume(body: _Resume):
        entries = conversations.sessions().get(body.session)
        if not entries:
            raise HTTPException(404, "No such conversation")
        await controller.switch_session(body.session)
        return {"messages": [{"user": e.get("user", ""), "assistant": e.get("assistant", "")}
                             for e in entries]}

    @app.post("/chat/speak")
    async def chat_speak(body: _Speak):
        # A blocking ElevenLabs call; keep it off the event loop.
        audio = await asyncio.to_thread(voice.generate_voice, body.text)
        return Response(audio, media_type="audio/mpeg")
