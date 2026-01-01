from dotenv import load_dotenv
load_dotenv()
import asyncio
import os
from agents.realtime import RealtimeAgent, RealtimeRunner

async def main():
    # 1. Define the Agent
    agent = RealtimeAgent(
        name="VersatileAssistant",
        instructions="You are a helpful assistant. If the user speaks to you, reply with voice. If they type, reply with text."
    )

    # 2. Setup the Runner with dual modalities
    runner = RealtimeRunner(
        starting_agent=agent,
        config={
            "model_settings": {
                "model_name": "gpt-realtime-mini",
                "voice": "alloy",
                "modalities": ["text", "audio"], # Enable both
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
            }
        }
    )

    # 3. Start the Session
    session = await runner.run()
    
    async with session:
        print("Session started. (Waiting for input...)")

        # Example: Sending a Text Message
        # This will trigger a text response event
        await session.send_message("Hello! Please respond in text.")

        # Example: Sending Audio (Pseudo-code for buffer)
        # await session.send_audio(audio_buffer)

        # 4. Handle incoming events based on type
        async for event in session:
            if event.type == "text_delta":
                # Handle text streaming
                print(f"Text Response: {event.text}", end="", flush=True)
            
            elif event.type == "audio_delta":
                # Handle audio streaming (send to speakers)
                # print("Receiving audio bits...")
                pass

            elif event.type == "response_done":
                print("\n[Response Cycle Finished]")

if __name__ == "__main__":
    asyncio.run(main())

