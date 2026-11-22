"""A small chat page for talking to Monika, meant to be embedded as an iframe
(the Home Assistant dashboard's webpage card). It posts to /prompt on the same
server; the Voice switch sets `speak` so the reply also plays on the room speaker.
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

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
const history = JSON.parse(localStorage.getItem("monika-chat") || "[]");

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
history.forEach(m => add(m.role, m.text));

async function submit() {
  const prompt = text.value.trim();
  if (!prompt || send.disabled) return;
  text.value = "";
  add("user", prompt);
  const pending = add("bot", "Thinking…", "pending");
  send.disabled = true;
  try {
    const r = await fetch("/prompt", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({prompt, speak: voice.checked,
                            attributes: {source: "homeassistant-dashboard"}}),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const reply = (await r.json()).message || "";
    pending.className = "msg bot";
    pending.textContent = reply;
    history.push({role: "user", text: prompt}, {role: "bot", text: reply});
    localStorage.setItem("monika-chat", JSON.stringify(history.slice(-50)));
  } catch (e) {
    pending.className = "msg bot error";
    pending.textContent = "Couldn't reach Monika (" + e.message + ")";
  }
  send.disabled = false;
  log.scrollTop = log.scrollHeight;
  text.focus();
}

document.getElementById("form").onsubmit = e => { e.preventDefault(); submit(); };
text.onkeydown = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } };
</script>
</body>
</html>
"""


def register(app: FastAPI) -> None:
    @app.get("/chat", response_class=HTMLResponse)
    async def chat_page():
        return HTMLResponse(_HTML)
