"""
Session 3 - Demo 5: Non-blocking (asynchronous) code
Compare the time with 04_async_blocking.py!
"""
import asyncio
import time

async def say_hello():
    await asyncio.sleep(2)  # Non-blocking sleep
    print("Hello World!")

async def say_good_bye():
    await asyncio.sleep(2)  # Non-blocking sleep
    print("GoodBye World!")

async def main():
    start = time.time()

    # Run both functions concurrently
    await asyncio.gather(say_hello(), say_good_bye())

    total = time.time() - start
    print(f"Total time for NON-BLOCKING version: {total:.2f} seconds")
    print("(Both functions ran concurrently!)")

# Run the async program
asyncio.run(main())
