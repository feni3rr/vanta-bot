import asyncio
import aiohttp

proxy = "http://127.0.0.1:10809"

async def test():
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                "https://api.telegram.org/bot8744880079:AAH0mSbtSGOmyacq-V0GSXxSUUzl9HgRjaY/getMe",
                proxy=proxy
            ) as resp:
                data = await resp.json()
                print(f"OK! @{data['result']['username']}")
                return True
    except Exception as e:
        print(f"ERR: {type(e).__name__}: {e}")
    return False

async def main():
    ok = await test()
    if ok:
        print("\nPROXY WORKS!")
    else:
        print("\nPROXY FAILED")

asyncio.run(main())
