import os
from controller import Controller
from dotenv import load_dotenv
from credentials import read_key
import asyncio

load_dotenv()

# The Claude Agent SDK's `claude` CLI authenticates via ANTHROPIC_API_KEY.
_anthropic_key = read_key("anthropic.key")
if _anthropic_key:
    os.environ["ANTHROPIC_API_KEY"] = _anthropic_key

c = Controller()
async def run():
    while True:
        msg = input("Prompt > ")
        response = await c.prompt(msg)
        print(response)
asyncio.run(run())