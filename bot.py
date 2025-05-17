import json
import os
import datetime
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

MEMORY_FILE = "ai_memory.json"
HISTORY_FILE = "chat_history.json"
GREET_FILE = "last_greet.txt"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def save_history(user_input, bot_response):
    entry = {
        "time": datetime.datetime.now().isoformat(),
        "user": user_input,
        "bot": bot_response
    }
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def greeted_today():
    try:
        with open(GREET_FILE, "r") as f:
            return f.read().strip() == datetime.date.today().isoformat()
    except:
        return False

def set_greeted_today():
    with open(GREET_FILE, "w") as f:
        f.write(datetime.date.today().isoformat())

def generate_greeting(user_input):
    if any(w in user_input.lower() for w in ["привет", "здравствуй", "добрый день"]):
        return "Привет!"
    return "Привет!"

def search_duckduckgo(query):
    logging.info("Поиск: %s", query)
    url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        results = soup.find_all("a", {"class": "result__a"}, limit=1)
        if results:
            return scrape_text_from_link(results[0]["href"])
        return "Не смог найти ответ."
    except Exception as e:
        return f"Ошибка поиска: {e}"

def scrape_text_from_link(url):
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        paragraphs = soup.find_all("p")
        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 40:
                return text
        return "Сайт найден, но без полезной информации."
    except Exception as e:
        return f"Ошибка загрузки сайта: {e}"

ASKING_CORRECTION = 1

user_memory = load_memory()
pending_question = {}
pending_answer = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я учусь с каждым вопросом. Напиши что хочешь узнать!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_memory, pending_question, pending_answer

    user_input = update.message.text.strip()
    chat_id = update.effective_chat.id

    if not greeted_today():
        greeting = generate_greeting(user_input)
        set_greeted_today()
    else:
        greeting = ""

    if user_input in user_memory:
        entry = user_memory[user_input]
        answer = entry["answer"] if isinstance(entry, dict) else entry
    else:
        answer = search_duckduckgo(user_input)

    full_response = f"{greeting} {answer}".strip()
    await update.message.reply_text(full_response)

    pending_question[chat_id] = user_input
    pending_answer[chat_id] = answer

    await update.message.reply_text("Это правильно? (да/нет/исправь)")
    return ASKING_CORRECTION

async def correction_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_memory, pending_question, pending_answer

    chat_id = update.effective_chat.id
    user_reply = update.message.text.strip().lower()

    if chat_id not in pending_question:
        await update.message.reply_text("Нет активного вопроса.")
        return ConversationHandler.END

    question = pending_question[chat_id]
    answer = pending_answer[chat_id]

    if user_reply == "да":
        user_memory[question] = {"answer": answer, "trust": 1.0}
        save_memory(user_memory)
        save_history(question, answer)
        await update.message.reply_text("Отлично, запомнил!")
        return ConversationHandler.END

    elif user_reply in ["нет", "исправь"]:
        await update.message.reply_text("Введи правильный ответ:")
        return ASKING_CORRECTION + 1

    else:
        await update.message.reply_text("Ок, не буду запоминать.")
        return ConversationHandler.END

async def receive_correction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_memory, pending_question

    chat_id = update.effective_chat.id
    correct_answer = update.message.text.strip()

    if chat_id not in pending_question:
        await update.message.reply_text("Нет активного запроса.")
        return ConversationHandler.END

    question = pending_question[chat_id]
    user_memory[question] = {"answer": correct_answer, "trust": 1.0}
    save_memory(user_memory)
    save_history(question, correct_answer)

    await update.message.reply_text("Спасибо! Исправил и запомнил.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            ASKING_CORRECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, correction_response)],
            ASKING_CORRECTION + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_correction)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
