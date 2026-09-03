import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

TOKEN = "8744880079:AAH0mSbtSGOmyacq-V0GSXxSUUzl9HgRjaY"
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

@router.message(CommandStart())
async def test_handler(m: Message):
    await m.answer("Test OK!")

dp.include_router(router)

async def main():
    me = await bot.get_me()
    print(f"Bot: @{me.username} (id={me.id})")
    updates = await bot.get_updates(limit=5)
    print(f"Pending updates: {len(updates)}")
    for u in updates:
        msg = u.message.text if u.message else "no"
        print(f"  update_id={u.update_id} msg={msg}")
    await bot.session.close()

asyncio.run(main())
