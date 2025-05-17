import json
import os
import datetime
import logging
import requests
import threading
from bs4 import BeautifulSoup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Try to load token from different locations
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    # Check if token exists in current directory .env file
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('BOT_TOKEN='):
                    TOKEN = line.strip().split('=', 1)[1]
                    break

# Check token validity
if not TOKEN:
    logger.warning("No Telegram BOT_TOKEN found in environment variables")
    TOKEN = "dummy_token_for_testing"  # Will be replaced when the actual token is available
else:
    logger.info(f"Loaded Telegram token: {TOKEN[:5]}...")

MEMORY_FILE = "ai_memory.json"
HISTORY_FILE = "chat_history.json"
GREET_FILE = "last_greet.txt"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Global lock for file operations to prevent race conditions
memory_lock = threading.Lock()
history_lock = threading.Lock()

def load_memory():
    with memory_lock:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    logging.error("Error parsing memory file, returning empty dict")
                    return {}
        return {}

def save_memory(memory):
    with memory_lock:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)

def save_history(user_input, bot_response, user_id=None):
    entry = {
        "time": datetime.datetime.now().isoformat(),
        "user": user_input,
        "bot": bot_response,
        "user_id": user_id
    }
    
    with history_lock:
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                try:
                    history = json.load(f)
                except json.JSONDecodeError:
                    logging.error("Error parsing history file, starting with empty history")
                    history = []
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
    now = datetime.datetime.now()
    hour = now.hour
    
    if hour < 6:
        time_greeting = "Доброй ночи!"
    elif hour < 12:
        time_greeting = "Доброе утро!"
    elif hour < 18:
        time_greeting = "Добрый день!"
    else:
        time_greeting = "Добрый вечер!"
        
    if any(w in user_input.lower() for w in ["привет", "здравствуй", "добрый день", "доброе утро", "добрый вечер"]):
        return time_greeting
    return time_greeting

def search_duckduckgo(query):
    logging.info("Поиск: %s", query)
    
    try:
        # URL encode the query to ensure it's properly formatted
        from urllib.parse import quote
        encoded_query = quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
        # Make the request with timeout
        res = requests.get(url, headers=headers, timeout=10)
        
        # Check response status code
        if res.status_code != 200:
            return f"Ошибка поиска: HTTP статус {res.status_code}"
        
        # Parse the HTML content
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Find results - these are the links to external sites
        results = soup.select("a.result__a")
        
        # If no results found
        if not results:
            logging.warning("Поиск не дал результатов для: %s", query)
            return "Не смог найти информацию по вашему запросу. Попробуйте переформулировать вопрос."
        
        # Try to get content from the top 3 results until we find something useful
        for i, result in enumerate(results[:3]):
            try:
                # Get the link URL
                link = result.get('href')
                if not link:
                    continue
                
                # Try to scrape text from the link
                text = scrape_text_from_link(link)
                if text and len(text) > 20 and not text.startswith("Ошибка"):
                    return text
            except Exception as e:
                logging.error(f"Error processing result {i}: {str(e)}")
                continue
        
        # If no useful content found from any link
        return "Нашел несколько ссылок, но не смог извлечь полезную информацию."
        
    except requests.exceptions.Timeout:
        logging.error("Timeout during search for: %s", query)
        return "Поиск занял слишком много времени. Пожалуйста, попробуйте позже."
    except requests.exceptions.RequestException as e:
        logging.error("Request error during search: %s", str(e))
        return f"Ошибка при поиске: {str(e)}"
    except Exception as e:
        logging.error("Unexpected error during search: %s", str(e))
        return f"Произошла неожиданная ошибка: {str(e)}"

def scrape_text_from_link(url):
    # Basic safety check for URL
    if not url or not (url.startswith('http://') or url.startswith('https://')):
        return "Неверный формат URL."
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
        logging.info(f"Scraping URL: {url}")
        res = requests.get(url, headers=headers, timeout=8)
        
        if res.status_code != 200:
            return f"Ошибка при открытии сайта: HTTP статус {res.status_code}"
            
        # Simple content extraction to avoid BeautifulSoup parsing issues
        content = res.text
        
        # Create soup for parsing
        soup = BeautifulSoup(content, "html.parser")
        
        # Extract plain text content
        for tag in soup(["script", "style", "header", "footer", "nav"]):
            tag.decompose()
            
        # Get text paragraphs
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
        
        # Filter meaningful paragraphs
        good_paragraphs = []
        for p in paragraphs:
            if len(p) > 40 and not "cookie" in p.lower() and not "copyright" in p.lower():
                good_paragraphs.append(p)
                
        # If we found good paragraphs, return them
        if good_paragraphs:
            result = " ".join(good_paragraphs[:3])
            if len(result) > 500:
                result = result[:497] + "..."
            return result
            
        # Otherwise try to get content from list items
        list_items = [li.get_text(strip=True) for li in soup.find_all("li")]
        good_items = [f"• {item}" for item in list_items if len(item) > 20]
            
        if good_items:
            result = "\n".join(good_items[:5])
            if len(result) > 500:
                result = result[:497] + "..."
            return result
            
        # Last resort - extract some visible text
        text = soup.get_text(separator=' ', strip=True)
        if len(text) > 100:
            return text[:497] + "..."
            
        return "Сайт найден, но не удалось извлечь полезную информацию."
        
    except requests.exceptions.Timeout:
        return "Сайт загружается слишком долго."
    except requests.exceptions.RequestException as e:
        return f"Ошибка при загрузке сайта: {str(e)}"
    except Exception as e:
        logging.error("Error scraping site: %s", str(e))
        return "Не удалось обработать сайт из-за технической ошибки."

ASKING_CORRECTION = 1

user_memory = load_memory()
pending_question = {}
pending_answer = {}

def start(update, context):
    update.message.reply_text("Привет! Я учусь с каждым вопросом. Напиши что хочешь узнать!")

def handle_message(update, context):
    global user_memory, pending_question, pending_answer

    user_input = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else None

    if not greeted_today():
        greeting = generate_greeting(user_input)
        set_greeted_today()
    else:
        greeting = ""

    # Check if we have this exact question in memory
    if user_input in user_memory:
        entry = user_memory[user_input]
        answer = entry["answer"] if isinstance(entry, dict) else entry
        logging.info("Using cached answer for: %s", user_input)
    else:
        # Not in memory, search online
        answer = search_duckduckgo(user_input)
        logging.info("Got new answer for: %s", user_input)

    full_response = f"{greeting} {answer}".strip()
    update.message.reply_text(full_response)

    # Store the pending question and answer for potential correction
    pending_question[chat_id] = user_input
    pending_answer[chat_id] = answer

    update.message.reply_text("Это правильный ответ? (да/нет/исправь)")
    return ASKING_CORRECTION

def correction_response(update, context):
    global user_memory, pending_question, pending_answer

    chat_id = update.effective_chat.id
    user_reply = update.message.text.strip().lower()
    user_id = update.effective_user.id if update.effective_user else None

    if chat_id not in pending_question:
        update.message.reply_text("Нет активного вопроса.")
        return ConversationHandler.END

    question = pending_question[chat_id]
    answer = pending_answer[chat_id]

    if user_reply == "да":
        user_memory[question] = {"answer": answer, "trust": 1.0}
        save_memory(user_memory)
        save_history(question, answer, user_id)
        update.message.reply_text("Отлично, запомнил!")
        return ConversationHandler.END

    elif user_reply in ["нет", "исправь"]:
        update.message.reply_text("Введи правильный ответ:")
        return ASKING_CORRECTION + 1

    else:
        update.message.reply_text("Ок, не буду запоминать.")
        return ConversationHandler.END

def receive_correction(update, context):
    global user_memory, pending_question

    chat_id = update.effective_chat.id
    correct_answer = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else None

    if chat_id not in pending_question:
        update.message.reply_text("Нет активного запроса.")
        return ConversationHandler.END

    question = pending_question[chat_id]
    user_memory[question] = {"answer": correct_answer, "trust": 1.0}
    save_memory(user_memory)
    save_history(question, correct_answer, user_id)

    update.message.reply_text("Спасибо! Исправил и запомнил.")
    return ConversationHandler.END

def main():
    global TOKEN
    
    try:
        # Double-check token is available (reload from .env if needed)
        if not TOKEN or TOKEN == "dummy_token_for_testing":
            # Reload token directly from .env file
            if os.path.exists('.env'):
                with open('.env', 'r') as f:
                    for line in f:
                        if line.startswith('BOT_TOKEN='):
                            TOKEN = line.strip().split('=', 1)[1].strip()
                            break
        
        if not TOKEN or TOKEN == "dummy_token_for_testing":
            logger.error("Cannot start bot: No valid Telegram token found")
            raise ValueError("No valid Telegram token available")
        
        # Create the Updater and pass it your bot's token
        logger.info(f"Starting Telegram bot with token: {TOKEN[:5]}...")
        updater = Updater(TOKEN)
        
        # Get the dispatcher to register handlers
        dp = updater.dispatcher
        
        # Register conversation handler
        conv = ConversationHandler(
            entry_points=[MessageHandler(Filters.text & ~Filters.command, handle_message)],
            states={
                ASKING_CORRECTION: [MessageHandler(Filters.text & ~Filters.command, correction_response)],
                ASKING_CORRECTION + 1: [MessageHandler(Filters.text & ~Filters.command, receive_correction)],
            },
            fallbacks=[CommandHandler("start", start)]
        )
        
        # Register handlers
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(conv)
        
        # Start the Bot
        print("Бот запущен на токене:", TOKEN[:5] + "...")
        logger.info("Starting polling for Telegram messages...")
        updater.start_polling()
        logger.info("Bot polling started successfully")
        
        # Run the bot until you press Ctrl-C
        # updater.idle()
        return True
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        print(f"Ошибка запуска бота: {e}")
        return False

if __name__ == "__main__":
    main()
