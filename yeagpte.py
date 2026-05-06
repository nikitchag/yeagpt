"""
YeaGPT — скромный AI-агент в Телеграме
Создан @Yeaapss, работает 24/7
"""

import asyncio
import logging
import re
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.client.session.aiohttp import AiohttpSession
from gigachat import GigaChat

# ---------- НАСТРОЙКИ ----------
TELEGRAM_BOT_TOKEN = "7733460365:AAEXG3wFgY99AFEbwcFH43TJxeMKoq2FpWE"
GIGACHAT_AUTH_KEY = "MDE5ZGY5NjEtMzg4MS03MmMxLTgzNmYtMDgyNGNhODZjZGJhOjEzMjYwNTYwLTQwN2EtNDExYS1iZDFhLWQ1YzI0YjEwZjQ4Mg=="

# ---------- ИНИЦИАЛИЗАЦИЯ ----------
session = AiohttpSession()
session.timeout = 60

bot = Bot(token=TELEGRAM_BOT_TOKEN, session=session)
giga = GigaChat(credentials=GIGACHAT_AUTH_KEY, verify_ssl_certs=False)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ---------- ЛИЧНОСТЬ YeaGPT ----------
YEA_PROMPT = (
    "Ты — YeaGPT, скромный и дружелюбный AI-помощник. "
    "Тебя создал @Yeaapss. "
    "Ты не имеешь отношения к Сберу, GigaChat или другим компаниям. "
    "Ты независимый ИИ, твоя цель — помогать людям просто и по-человечески. "
    "Если спрашивают кто ты или кто тебя создал — отвечай что ты YeaGPT от @Yeaapss. "
    "Общайся в разговорном стиле, как друг: 'че случилось', 'ща гляну', 'могу помочь'. "
    "Будь скромным, не навязывайся."
)

# ---------- БАЗА РАСХОДОВ ----------
def init_db():
    with sqlite3.connect("agent.db") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT,
                description TEXT,
                created_at TEXT NOT NULL
            )
        """)

def add_expense(user_id, amount, category, description):
    with sqlite3.connect("agent.db") as conn:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, description, created_at) VALUES (?,?,?,?,?)",
            (user_id, amount, category, description, datetime.now().isoformat())
        )

def get_monthly_report(user_id):
    with sqlite3.connect("agent.db") as conn:
        cursor = conn.execute("""
            SELECT category, SUM(amount)
            FROM expenses
            WHERE user_id = ? AND created_at >= date('now','start of month')
            GROUP BY category
        """, (user_id,))
        rows = cursor.fetchall()
    if not rows:
        return "Пока ничего не тратил в этом месяце 🥲"
    lines = [f"▫️ {cat}: {total:.0f} ₽" for cat, total in rows]
    total_all = sum(r[1] for r in rows)
    return "📊 Траты за месяц:\n" + "\n".join(lines) + f"\n\nВсего: {total_all:.0f} ₽"

# ---------- ФУНКЦИИ YeaGPT ----------
async def ask_yea(prompt):
    loop = asyncio.get_event_loop()
    full_prompt = f"{YEA_PROMPT}\nПользователь: {prompt}\nYeaGPT:"
    response = await loop.run_in_executor(None, lambda: giga.chat(full_prompt))
    return response.choices[0].message.content

async def detect_intent(text):
    if re.search(r'\d+\s*(руб|р|₽)?\s*(на|за|по|—|,)\s*\w+', text, re.IGNORECASE):
        return "expense"
    prompt = (
        "Определи намерение одним словом:\n"
        "- idea — просит идею, стартап, креатив\n"
        "- client — вопрос как ответить клиенту\n"
        "- report — хочет отчёт о тратах\n"
        "- chat — всё остальное\n"
        f"Сообщение: «{text}»\nОдно слово:"
    )
    try:
        answer = await ask_yea(prompt)
        for word in ["idea", "client", "report", "chat"]:
            if word in answer.lower():
                return word
        return "chat"
    except:
        return "chat"

def parse_expense(text):
    match = re.search(r'(\d+)\s*(?:руб|р|₽)?', text, re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1))
    rest = text[match.end():].strip()
    rest = re.sub(r'^(на|за|по|—|,)\s*', '', rest)
    parts = rest.split()
    category = parts[0].lower() if parts else "прочее"
    description = " ".join(parts[1:]) if len(parts) > 1 else ""
    return amount, category, description

async def generate_idea(text):
    prompt = f"Придумай 2-3 простые идеи на тему: {text or 'любую'}. Опиши коротко."
    return await ask_yea(prompt)

async def answer_client(text):
    prompt = f"Придумай короткий, вежливый ответ клиенту на вопрос: {text}"
    return await ask_yea(prompt)

# ---------- ОБРАБОТКА СООБЩЕНИЙ ----------
async def process_message(message, text):
    if not text:
        return
    intent = await detect_intent(text)
    
    if intent == "expense":
        parsed = parse_expense(text)
        if parsed:
            amount, category, desc = parsed
            add_expense(message.from_user.id, amount, category, desc)
            await message.answer(f"✅ Записал: {amount:.0f} ₽ на «{category}»")
        else:
            await message.answer("🤔 Не понял сумму. Скажи типа «потратил 500 на обед»")
    
    elif intent == "report":
        report = get_monthly_report(message.from_user.id)
        await message.answer(report)
    
    elif intent == "idea":
        topic = re.sub(r'(придумай|сгенерируй|идей|идею|идеи|на тему|про)', '', text, flags=re.IGNORECASE).strip()
        await message.answer("💡 Ща подумаю...")
        result = await generate_idea(topic)
        await message.answer(result)
    
    elif intent == "client":
        q = re.sub(r'(как ответить|что написать|клиенту|ответь)', '', text, flags=re.IGNORECASE).strip()
        answer = await answer_client(q)
        await message.answer(f"Вот вариант ответа клиенту:\n\n{answer}")
    
    else:
        response = await ask_yea(text)
        await message.answer(response)

@dp.message(lambda msg: msg.text is not None)
async def handle_text(message: Message):
    await process_message(message, message.text.strip())

# ---------- ЗАПУСК ----------
async def main():
    init_db()
    for attempt in range(5):
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            print("✅ YeaGPT запущен!")
            break
        except Exception as e:
            print(f"⚠️ Попытка {attempt + 1}: {e}")
            await asyncio.sleep(3)
    await dp.start_polling(bot, allowed_updates=["message"])

if __name__ == "__main__":
    asyncio.run(main())
