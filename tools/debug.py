from controller import Controller
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Deliberately no ANTHROPIC_API_KEY here: see server.py.

c = Controller()
async def run():
    while True:
        msg = input("Prompt > ")
        response = await c.prompt(msg)
        print(response)
asyncio.run(run())