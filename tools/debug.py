from controller import Controller
from dotenv import load_dotenv
import asyncio

load_dotenv()

c = Controller()
async def run():
    while True:
        msg = input("Prompt > ")
        response = await c.prompt(msg)
        print(response)
asyncio.run(run())