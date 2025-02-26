import asyncio
import logging
import sqlite3
import os
from datetime import datetime, time as datetime_time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import requests
from dotenv import load_dotenv
import nest_asyncio  # Фікс для MacOS

nest_asyncio.apply()

# Завантаження змінних середовища
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BOT_USERNAME = os.getenv("BOT_USERNAME")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))

if not TELEGRAM_TOKEN or not OPENROUTER_API_KEY or not BOT_USERNAME or CHANNEL_ID == 0:
    logging.error("❌ Відсутні необхідні змінні середовища. Перевірте .env файл.")
    exit(1)

# Налаштування логування
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Ініціалізація бази даних SQLite
conn = sqlite3.connect("posts.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    language TEXT,
    content TEXT
)
""")
conn.commit()

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привіт! Я ваш SMM-бот.")

async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text("Команди: /start, /help, /settings, /reklama, /addpost.")

async def settings(update: Update, context: CallbackContext):
    await update.message.reply_text("Тут будуть налаштування.")

async def reklama(update: Update, context: CallbackContext):
    await update.message.reply_text("Тут буде обробка рекламних запитів.")

async def add_post(update: Update, context: CallbackContext):
    post_content = "Приклад навчального поста"
    language = 'ru'
    cursor.execute("INSERT INTO posts (date, language, content) VALUES (?, ?, ?)", (datetime.now(), language, post_content))
    conn.commit()
    await update.message.reply_text("✅ Пост додано в базу!")

async def chatgpt_response(update: Update, context: CallbackContext):
    user_message = update.message.text
    try:
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
        data = {
            "model": "openrouter/gpt-4o",  # Модель можна змінити
            "messages": [{"role": "user", "content": user_message}],
            "temperature": 0.7
        }
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers)
        ai_response = response.json().get("choices", [{}])[0].get("message", {}).get("content", "⚠️ Помилка отримання відповіді")
        await update.message.reply_text(ai_response)
    except Exception as e:
        logger.error(f"OpenRouter API error: {e}")
        await update.message.reply_text("⚠️ Помилка підключення до AI. Спробуйте ще раз.")

async def daily_posting(context: CallbackContext):
    cursor.execute("SELECT content FROM posts WHERE language = ? ORDER BY date DESC LIMIT 1", ('ru',))
    post = cursor.fetchone()
    if post:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("💬 Почати чат із ботом", url=f"https://t.me/{BOT_USERNAME}")]]
        )
        await context.bot.send_message(chat_id=CHANNEL_ID, text=post[0], reply_markup=keyboard)
    else:
        await context.bot.send_message(chat_id=CHANNEL_ID, text="❌ Немає постів для відправки.")

async def start_daily_posting(application: Application):
    application.job_queue.run_daily(daily_posting, time=datetime_time(9, 0, 0))

async def error(update: Update, context: CallbackContext):
    logger.warning(f"❌ Помилка: {context.error}")

async def main():
    print("🔹 Бот запускається...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("reklama", reklama))
    app.add_handler(CommandHandler("addpost", add_post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chatgpt_response))

    await start_daily_posting(app)
    app.add_error_handler(error)

    logger.info("✅ Бот запущено...")
    async with app:
        await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
