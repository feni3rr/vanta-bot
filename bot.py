import asyncio
import sqlite3
import uuid
import logging
import certifi
import os
import json
from datetime import datetime, timedelta
from aiohttp import web

os.environ["SSL_CERT_FILE"] = certifi.where()

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

TOKEN = "8744880079:AAH0mSbtSGOmyacq-V0GSXxSUUzl9HgRjaY"
ADMIN_ID = 8417977802
VALIDATE_AUTH = os.environ.get("VALIDATE_AUTH", "vanta-internal-2024")
CARD_NUMBER = "2200 7012 2380 0894"
CARDHOLDER = "Сергей М."

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

logging.basicConfig(level=logging.INFO)

# --- Database ---
db = sqlite3.connect("licenses.db")
db.execute("""CREATE TABLE IF NOT EXISTS licenses (
    key TEXT PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    plan TEXT,
    created_at TEXT,
    expires_at TEXT,
    active INTEGER DEFAULT 1
)""")
db.execute("""CREATE TABLE IF NOT EXISTS pending (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    plan TEXT,
    created_at TEXT
)""")
db.commit()


def generate_key():
    parts = [uuid.uuid4().hex[:8].upper() for _ in range(3)]
    return f"VANTA-{parts[0]}-{parts[1]}-{parts[2]}"


def get_plan_days(plan):
    return {"1m": 30, "3m": 90, "life": 99999}.get(plan, 30)


def get_plan_name(plan):
    return {"1m": "1 месяц", "3m": "3 месяца", "life": "Навсегда"}.get(plan, plan)


def get_plan_price(plan):
    return {"1m": "50₽", "3m": "110₽", "life": "150₽"}.get(plan, "?")


# --- Keyboards ---
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить клиент", callback_data="buy")],
        [InlineKeyboardButton(text="🔑 Проверить лицензию", callback_data="check")],
        [InlineKeyboardButton(text="💬 Поддержка", url="t.me/feni3_r")],
    ])


def buy_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц — 50₽", callback_data="plan_1m")],
        [InlineKeyboardButton(text="3 месяца — 110₽", callback_data="plan_3m")],
        [InlineKeyboardButton(text="Навсегда — 150₽", callback_data="plan_life")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")],
    ])


def confirm_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выдать", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}"),
        ],
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔑 Генерировать ключ", callback_data="admin_gen")],
    ])


# --- User handlers ---
@router.message(CommandStart())
async def cmd_start(m: Message):
    text = (
        f"🎮 <b>VantaClient</b>\n\n"
        f"Привет, <b>{m.from_user.first_name}</b>!\n"
        f"Это бот для покупки клиента VantaClient.\n\n"
        f"📋 <b>Тарифы:</b>\n"
        f"  • 1 месяц — 50₽\n"
        f"  • 3 месяца — 110₽\n"
        f"  • Навсегда — 150₽\n\n"
        f"Выбери действие:"
    )
    await m.answer(text, reply_markup=main_kb())


@router.callback_query(F.data == "back")
async def cb_back(c: CallbackQuery):
    text = (
        f"🎮 <b>VantaClient</b>\n\n"
        f"Выбери действие:"
    )
    await c.message.edit_text(text, reply_markup=main_kb())
    await c.answer()


@router.callback_query(F.data == "buy")
async def cb_buy(c: CallbackQuery):
    text = (
        "🛒 <b>Выбери тариф:</b>\n\n"
        "📋 <b>Тарифы:</b>\n"
        "  • 1 месяц — 50₽\n"
        "  • 3 месяца — 110₽\n"
        "  • Навсегда — 150₽\n\n"
        "После оплаты админ проверит и выдаст ключ."
    )
    await c.message.edit_text(text, reply_markup=buy_kb())
    await c.answer()


@router.callback_query(F.data.startswith("plan_"))
async def cb_plan(c: CallbackQuery):
    plan = c.data.replace("plan_", "")
    username = c.from_user.username or c.from_user.first_name
    db.execute(
        "INSERT OR REPLACE INTO pending (user_id, username, plan, created_at) VALUES (?, ?, ?, ?)",
        (c.from_user.id, username, plan, datetime.now().isoformat())
    )
    db.commit()

    text = (
        f"📝 <b>Заявка создана!</b>\n\n"
        f"Тариф: <b>{get_plan_name(plan)}</b>\n"
        f"Цена: <b>{get_plan_price(plan)}</b>\n\n"
        f"💳 Переведи на карту Т-Банк:\n"
        f"<code>{CARD_NUMBER}</code>\n"
        f"Получатель: {CARDHOLDER}\n\n"
        f"После оплаты нажми «Оплатил» — админ проверит и выдаст ключ."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатил", callback_data=f"paid_{c.from_user.id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")],
    ])
    await c.message.edit_text(text, reply_markup=kb)
    await c.answer()

    # Notify admin
    admin_text = (
        f"📩 <b>Новая заявка!</b>\n\n"
        f"Пользователь: @{username} (ID: {c.from_user.id})\n"
        f"Тариф: {get_plan_name(plan)}\n"
        f"Цена: {get_plan_price(plan)}\n\n"
        f"Нажми «Выдать» после получения оплаты."
    )
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=confirm_kb(c.from_user.id))


@router.callback_query(F.data.startswith("paid_"))
async def cb_paid(c: CallbackQuery):
    await c.answer("Жди подтверждения от админа!", show_alert=True)


@router.callback_query(F.data == "check")
async def cb_check(c: CallbackQuery):
    row = db.execute(
        "SELECT key, plan, expires_at, active FROM licenses WHERE user_id = ? AND active = 1",
        (c.from_user.id,)
    ).fetchone()

    if not row:
        await c.message.edit_text(
            "🔑 <b>У тебя нет активных лицензий.</b>\n\nКупи клиент чтобы получить ключ!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛒 Купить", callback_data="buy")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back")],
            ])
        )
        await c.answer()
        return

    key, plan, expires, active = row
    exp_date = datetime.fromisoformat(expires).strftime("%d.%m.%Y")
    text = (
        f"🔑 <b>Твоя лицензия:</b>\n\n"
        f"Ключ: <code>{key}</code>\n"
        f"Тариф: <b>{get_plan_name(plan)}</b>\n"
        f"Действует до: <b>{exp_date}</b>\n"
        f"Статус: ✅ Активна"
    )
    await c.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")],
    ]))
    await c.answer()


# --- Admin handlers ---
@router.message(Command("admin"))
async def cmd_admin(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    await m.answer("🔧 <b>Панель админа</b>", reply_markup=admin_kb())


@router.callback_query(F.data == "admin_stats")
async def cb_stats(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Нет доступа!", show_alert=True)

    total = db.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
    active = db.execute("SELECT COUNT(*) FROM licenses WHERE active = 1").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM pending").fetchone()[0]
    users = db.execute("SELECT COUNT(DISTINCT user_id) FROM licenses").fetchone()[0]

    text = (
        f"📊 <b>Статистика:</b>\n\n"
        f"Всего ключей: {total}\n"
        f"Активных: {active}\n"
        f"Ожидают оплаты: {pending}\n"
        f"Пользователей: {users}"
    )
    await c.message.edit_text(text, reply_markup=admin_kb())
    await c.answer()


@router.callback_query(F.data == "admin_gen")
async def cb_gen(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Нет доступа!", show_alert=True)

    key = generate_key()
    db.execute(
        "INSERT INTO licenses (key, user_id, username, plan, created_at, expires_at, active) VALUES (?, ?, ?, ?, ?, ?, 1)",
        (key, 0, "admin", "life", datetime.now().isoformat(), (datetime.now() + timedelta(days=99999)).isoformat())
    )
    db.commit()

    await c.message.edit_text(
        f"🔑 <b>Новый ключ:</b>\n\n<code>{key}</code>\n\nОтправь его пользователю.",
        reply_markup=admin_kb()
    )
    await c.answer()


@router.callback_query(F.data.startswith("approve_"))
async def cb_approve(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Нет доступа!", show_alert=True)

    user_id = int(c.data.split("_")[1])
    row = db.execute("SELECT plan, username FROM pending WHERE user_id = ?", (user_id,)).fetchone()

    if not row:
        await c.answer("Заявка не найдена!", show_alert=True)
        return

    plan, username = row
    key = generate_key()
    expires = datetime.now() + timedelta(days=get_plan_days(plan))

    db.execute(
        "INSERT INTO licenses (key, user_id, username, plan, created_at, expires_at, active) VALUES (?, ?, ?, ?, ?, ?, 1)",
        (key, user_id, username, plan, datetime.now().isoformat(), expires.isoformat())
    )
    db.execute("DELETE FROM pending WHERE user_id = ?", (user_id,))
    db.commit()

    # Notify user
    exp_date = expires.strftime("%d.%m.%Y")
    user_text = (
        f"✅ <b>Оплата подтверждена!</b>\n\n"
        f"Твой ключ:\n<code>{key}</code>\n\n"
        f"Тариф: <b>{get_plan_name(plan)}</b>\n"
        f"Действует до: <b>{exp_date}</b>\n\n"
        f"Введи его в клиенте для активации."
    )
    await bot.send_message(user_id, user_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Скачать клиент", url="t.me/feni3_r")],
    ]))

    await c.message.edit_text(
        f"✅ Ключ выдан!\n\nПользователь: @{username}\nКлюч: <code>{key}</code>",
        reply_markup=admin_kb()
    )
    await c.answer("Ключ выдан!")


@router.callback_query(F.data.startswith("reject_"))
async def cb_reject(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Нет доступа!", show_alert=True)

    user_id = int(c.data.split("_")[1])
    row = db.execute("SELECT username FROM pending WHERE user_id = ?", (user_id,)).fetchone()
    db.execute("DELETE FROM pending WHERE user_id = ?", (user_id,))
    db.commit()

    username = row[0] if row else "unknown"
    await bot.send_message(user_id, "❌ <b>Оплата не подтверждена.</b>\n\nСвяжись с поддержкой: @feni3_r")

    await c.message.edit_text(f"❌ Отклонено.\nПользователь: @{username}", reply_markup=admin_kb())
    await c.answer("Отклонено")


@router.message(Command("key"))
async def cmd_key(m: Message):
    args = m.text.split()
    if len(args) < 2:
        await m.answer("Использование: /key VANTA-XXXX-XXXX-XXXX")
        return

    key = args[1].upper()
    row = db.execute(
        "SELECT user_id, plan, expires_at, active FROM licenses WHERE key = ?", (key,)
    ).fetchone()

    if not row:
        await m.answer("❌ Ключ не найден.")
        return

    uid, plan, expires, active = row
    exp_date = datetime.fromisoformat(expires).strftime("%d.%m.%Y")

    if not active:
        await m.answer("❌ Ключ уже использован.")
        return

    if uid != 0 and uid != m.from_user.id and m.from_user.id != ADMIN_ID:
        await m.answer("❌ Этот ключ принадлежит другому пользователю.")
        return

    if datetime.now() > datetime.fromisoformat(expires):
        await m.answer("❌ Ключ истёк.")
        return

    # Activate for this user
    if uid == 0:
        db.execute("UPDATE licenses SET user_id = ?, username = ? WHERE key = ?",
                   (m.from_user.id, m.from_user.username or m.from_user.first_name, key))
        db.commit()

    await m.answer(
        f"✅ <b>Ключ активирован!</b>\n\n"
        f"Тариф: <b>{get_plan_name(plan)}</b>\n"
        f"Действует до: <b>{exp_date}</b>"
    )


async def main():
    dp.include_router(router)

    app = web.Application()
    app.router.add_post("/validate", validate_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"HTTP server on :{port}")
    print("Бот запущен!")
    await dp.start_polling(bot)


async def validate_handler(request):
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {VALIDATE_AUTH}":
        return web.json_response({"valid": False, "error": "unauthorized"}, status=401)

    try:
        data = await request.json()
        key = data.get("key", "").strip().upper()
    except Exception:
        return web.json_response({"valid": False, "error": "bad request"}, status=400)

    row = db.execute(
        "SELECT plan, expires_at, active FROM licenses WHERE key = ?", (key,)
    ).fetchone()

    if not row:
        return web.json_response({"valid": False, "error": "key not found"})

    plan, expires, active = row
    if not active:
        return web.json_response({"valid": False, "error": "key deactivated"})
    if datetime.now() > datetime.fromisoformat(expires):
        return web.json_response({"valid": False, "error": "key expired"})

    return web.json_response({
        "valid": True,
        "plan": plan,
        "expires_at": expires
    })


if __name__ == "__main__":
    asyncio.run(main())
