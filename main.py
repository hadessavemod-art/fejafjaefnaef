# main.py — версия под aiogram 2.x
# Запуск: pip install aiogram==2.25.1
#        python main.py

import asyncio
import logging
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============ КОНФИГ ============
BOT_TOKEN = "8807286672:AAEIss-kdTWHWpEWOOOuwHLKSqjK3JhcnLk"
SELLER_USERNAME = "@cryptoexchxnge"

# ============ ХРАНИЛИЩА ============
offers = {}
users = {}

# ============ ТЕКСТЫ ============
TEXTS = {
    "ru": {
        "menu": (
            "🎁 Gift Trade Bot\n\n"
            "Добро пожаловать!\n\n"
            "Здесь ты можешь управлять подпиской и получать инструкции по работе с ботом.\n\n"
            "Выбери нужный раздел ниже."
        ),
        "buy_sub": "🛍 Оформить подписку",
        "my_sub": "💳 Моя подписка",
        "offer": "Пользователь предлагает вам {price} ⭐ за подарок {name} #{id}.",
        "accept": "✅ Принять",
        "reject": "❌ Отклонить",
        "sold": (
            "🎁 Подарок: {name} #{id} успешно продан!\n\n"
            "Передайте подарок покупателю для зачисления звёзд.\n\n"
            "Инструкция:\n"
            "1. Открой свой профиль в Telegram\n"
            "2. Перейди в раздел «Подарки»\n"
            "3. Выбери подарок {name} #{id}\n"
            "4. Нажми «Передать» → выбери {seller}\n"
            "5. Подтверди передачу"
        ),
        "transfer": "📤 Передать NFT",
        "how": "❓ Как передать?",
        "done": "✅ NFT получен. Звёзды зачислены.",
        "rejected": "❌ Предложение отклонено.",
        "expired": "⌛ Предложение истекло.",
        "no_sub": "Нужна подписка. Оформи в меню.",
        "bad_link": "Неверная ссылка. Формат: .buy ru https://t.me/nft/Name-123 1000 stars",
        "need_reply": "Ответь командой .buy на сообщение продавца.",
        "sub_active": "✅ Подписка активна до {date}.",
        "sub_inactive": "❌ Подписка не активна.",
    },
    "en": {
        "menu": (
            "🎁 Gift Trade Bot\n\n"
            "Welcome!\n\n"
            "Here you can manage your subscription and get instructions.\n\n"
            "Choose a section below."
        ),
        "buy_sub": "🛍 Buy subscription",
        "my_sub": "💳 My subscription",
        "offer": "A user offers you {price} ⭐ for gift {name} #{id}.",
        "accept": "✅ Accept",
        "reject": "❌ Decline",
        "sold": (
            "🎁 Gift: {name} #{id} successfully sold!\n\n"
            "Transfer the gift to the buyer to receive stars.\n\n"
            "Instructions:\n"
            "1. Open your Telegram profile\n"
            "2. Go to «Gifts»\n"
            "3. Select gift {name} #{id}\n"
            "4. Tap «Transfer» → choose {seller}\n"
            "5. Confirm the transfer"
        ),
        "transfer": "📤 Transfer NFT",
        "how": "❓ How to transfer?",
        "done": "✅ NFT received. Stars credited.",
        "rejected": "❌ Offer declined.",
        "expired": "⌛ Offer expired.",
        "no_sub": "Subscription required. Buy it in the menu.",
        "bad_link": "Invalid link. Format: .buy en https://t.me/nft/Name-123 1000 stars",
        "need_reply": "Reply with .buy to the seller's message.",
        "sub_active": "✅ Subscription active until {date}.",
        "sub_inactive": "❌ Subscription not active.",
    },
}

# ============ ИНИЦИАЛИЗАЦИЯ ============
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

BUY_RE = re.compile(
    r"^\.buy\s+(?P<lang>ru|en)\s+(?P<link>https?://\S+)\s+(?P<price>\d+)\s*(?P<cur>stars|gram)?$",
    re.IGNORECASE
)


# ============ УТИЛИТЫ ============
def parse_nft_link(link: str):
    m = re.search(r"/nft/(?P<name>[A-Za-z]+)-(?P<id>\d+)", link)
    if not m:
        return None, None
    return m.group("name"), m.group("id")


def has_sub(uid: int) -> bool:
    u = users.get(uid, {})
    until = u.get("sub_until")
    return bool(until and until > datetime.utcnow())


def main_menu(lang: str = "ru"):
    t = TEXTS[lang]
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(text=t["buy_sub"], callback_data="sub:buy"),
        InlineKeyboardButton(text=t["my_sub"], callback_data="sub:my"),
    )
    return kb


def offer_kb(lang: str, offer_id: str):
    t = TEXTS[lang]
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text=t["reject"], callback_data=f"reject:{offer_id}"),
        InlineKeyboardButton(text=t["accept"], callback_data=f"accept:{offer_id}"),
    )
    return kb


def sold_kb(lang: str, offer_id: str):
    t = TEXTS[lang]
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(text=t["transfer"], callback_data=f"transfer:{offer_id}"),
        InlineKeyboardButton(text=t["how"], callback_data=f"how:{offer_id}"),
    )
    return kb


async def auto_expire(offer_id: str, seconds: int = 600):
    await asyncio.sleep(seconds)
    o = offers.get(offer_id)
    if o and o["status"] == "pending":
        o["status"] = "expired"


# ============ ХЕНДЛЕРЫ ============
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer(TEXTS["ru"]["menu"], reply_markup=main_menu("ru"))


@dp.callback_query_handler(lambda c: c.data == "sub:buy")
async def buy_sub(call: types.CallbackQuery):
    await call.answer("Оплата подписки — подключи Telegram Stars.", show_alert=True)


@dp.callback_query_handler(lambda c: c.data == "sub:my")
async def my_sub(call: types.CallbackQuery):
    uid = call.from_user.id
    if has_sub(uid):
        until = users[uid]["sub_until"]
        text = TEXTS["ru"]["sub_active"].format(date=until.strftime("%d.%m.%Y"))
    else:
        text = TEXTS["ru"]["sub_inactive"]
    await call.message.edit_text(text, reply_markup=main_menu("ru"))
    await call.answer()


@dp.message_handler(lambda m: m.text and m.text.startswith(".buy"))
async def buy_cmd(message: types.Message):
    if not has_sub(message.from_user.id):
        await message.answer(TEXTS["ru"]["no_sub"])
        return

    m = BUY_RE.match(message.text)
    if not m:
        await message.answer(TEXTS["ru"]["bad_link"])
        return

    lang = m.group("lang").lower()
    link = m.group("link")
    price = int(m.group("price"))
    cur = (m.group("cur") or "stars").lower()

    name, gift_id = parse_nft_link(link)
    if not name:
        await message.answer(TEXTS[lang]["bad_link"])
        return

    if not message.reply_to_message:
        await message.answer(TEXTS[lang]["need_reply"])
        return

    victim_id = message.reply_to_message.from_user.id
    offer_id = f"{message.from_user.id}_{gift_id}"

    offers[offer_id] = {
        "seller": message.from_user.id,
        "victim": victim_id,
        "name": name,
        "gift_id": gift_id,
        "price": price,
        "currency": cur,
        "lang": lang,
        "status": "pending",
        "created": datetime.utcnow(),
    }

    t = TEXTS[lang]
    text = t["offer"].format(price=price, name=name, id=gift_id)

    await bot.send_message(victim_id, text, reply_markup=offer_kb(lang, offer_id))
    await message.answer("✅ Оффер отправлен.")

    asyncio.create_task(auto_expire(offer_id, 600))


@dp.callback_query_handler(lambda c: c.data.startswith("accept:"))
async def accept(call: types.CallbackQuery):
    offer_id = call.data.split(":", 1)[1]
    o = offers.get(offer_id)
    if not o or o["status"] != "pending":
        await call.answer(TEXTS["ru"]["expired"], show_alert=True)
        return

    o["status"] = "accepted"
    t = TEXTS[o["lang"]]

    text = t["sold"].format(
        name=o["name"], id=o["gift_id"], seller=SELLER_USERNAME
    )
    await call.message.edit_text(text, reply_markup=sold_kb(o["lang"], offer_id))
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("reject:"))
async def reject(call: types.CallbackQuery):
    offer_id = call.data.split(":", 1)[1]
    o = offers.get(offer_id)
    if o:
        o["status"] = "rejected"
    await call.message.edit_text(TEXTS["ru"]["rejected"])
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("transfer:"))
async def transfer(call: types.CallbackQuery):
    offer_id = call.data.split(":", 1)[1]
    o = offers.get(offer_id)
    if not o:
        await call.answer(TEXTS["ru"]["expired"], show_alert=True)
        return

    o["status"] = "done"
    t = TEXTS[o["lang"]]
    await call.message.edit_text(t["done"])
    await call.answer()

    try:
        await bot.send_message(
            o["seller"],
            f"✅ NFT {o['name']} #{o['gift_id']} отправлен. Сделка завершена."
        )
    except Exception:
        pass


@dp.callback_query_handler(lambda c: c.data.startswith("how:"))
async def how(call: types.CallbackQuery):
    offer_id = call.data.split(":", 1)[1]
    o = offers.get(offer_id)
    if not o:
        await call.answer("Оффер не найден.", show_alert=True)
        return
    await call.answer(
        "Открой профиль → Подарки → выбери подарок → Передать → выбери продавца.",
        show_alert=True
    )


# ============ СТАРТ ============
if __name__ == "__main__":
    from aiogram import executor
    print("Бот офферов активен.")
    executor.start_polling(dp, skip_updates=True)
