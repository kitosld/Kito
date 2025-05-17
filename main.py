import os
import json
import logging
import threading
import time
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from datetime import datetime, date, timedelta
# Import bot module in a try-except to prevent startup errors
try:
    import bot
except ImportError:
    import logging
    logging.error("Could not import bot module. Telegram functionality will be limited.")
    # Create dummy bot module with required attributes
    class DummyBot:
        MEMORY_FILE = "ai_memory.json"
        HISTORY_FILE = "chat_history.json"
        
        @staticmethod
        def main():
            print("Dummy bot started")
    
    bot = DummyBot

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "self_learning_bot_secret")

# Global variables
bot_thread = None
bot_running = False

@app.route('/')
def index():
    """Render dashboard home page"""
    return render_template('index.html', bot_running=bot_running, now=datetime.now())

@app.route('/start_bot', methods=['POST'])
def start_bot():
    """Start the Telegram bot in a separate thread"""
    global bot_thread, bot_running
    
    if not bot_running:
        try:
            # Start the bot in a separate thread
            bot_thread = threading.Thread(target=bot.main)
            bot_thread.daemon = True
            bot_thread.start()
            
            # Wait a moment to see if the bot starts successfully
            time.sleep(1)
            
            # Set the status based on bot's return value or exception
            bot_running = True
            flash("Bot started successfully! Check your Telegram app by sending a message to the bot.", "success")
            logging.info("Bot thread started successfully")
            
            # Instructions for user
            if hasattr(bot, 'TOKEN') and bot.TOKEN and ':' in bot.TOKEN:
                bot_username = bot.TOKEN.split(':')[0]
                flash(f"Find the bot by searching for @{bot_username} on Telegram", "info")
            else:
                flash("Use the Telegram bot token from your .env file", "info")
            
        except Exception as e:
            flash(f"Failed to start bot: {str(e)}", "danger")
            logging.error(f"Error starting bot: {str(e)}")
    else:
        flash("Bot is already running! You can use it in Telegram.", "warning")
    
    return redirect(url_for('index'))

@app.route('/history')
def history():
    """Render chat history page"""
    history_data = []
    if os.path.exists(bot.HISTORY_FILE):
        with open(bot.HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                history_data = json.load(f)
            except json.JSONDecodeError:
                history_data = []
    
    # Sort by time in descending order (most recent first)
    history_data.sort(key=lambda x: x.get('time', ''), reverse=True)
    
    return render_template('history.html', history=history_data, now=datetime.now())

@app.route('/memory')
def memory():
    """Render bot memory page"""
    memory_data = {}
    if os.path.exists(bot.MEMORY_FILE):
        with open(bot.MEMORY_FILE, "r", encoding="utf-8") as f:
            try:
                memory_data = json.load(f)
            except json.JSONDecodeError:
                memory_data = {}
    
    # Convert to list for easier template rendering
    memory_list = []
    for question, data in memory_data.items():
        if isinstance(data, dict):
            memory_list.append({
                'question': question,
                'answer': data.get('answer', ''),
                'trust': data.get('trust', 0.0)
            })
        else:
            memory_list.append({
                'question': question,
                'answer': data,
                'trust': 1.0
            })
    
    # Sort by question alphabetically
    memory_list.sort(key=lambda x: x['question'])
    
    return render_template('memory.html', memory=memory_list, now=datetime.now())

@app.route('/delete_memory/<question>', methods=['POST'])
def delete_memory(question):
    """Delete a specific memory entry"""
    memory_data = {}
    if os.path.exists(bot.MEMORY_FILE):
        with open(bot.MEMORY_FILE, "r", encoding="utf-8") as f:
            try:
                memory_data = json.load(f)
            except json.JSONDecodeError:
                memory_data = {}
    
    if question in memory_data:
        del memory_data[question]
        with open(bot.MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory_data, f, ensure_ascii=False, indent=2)
        flash("Memory entry deleted successfully!", "success")
    else:
        flash("Memory entry not found!", "danger")
    
    return redirect(url_for('memory'))

@app.route('/edit_memory', methods=['POST'])
def edit_memory():
    """Edit a memory entry"""
    question = request.form.get('question')
    answer = request.form.get('answer')
    trust = float(request.form.get('trust', 1.0))
    
    memory_data = {}
    if os.path.exists(bot.MEMORY_FILE):
        with open(bot.MEMORY_FILE, "r", encoding="utf-8") as f:
            try:
                memory_data = json.load(f)
            except json.JSONDecodeError:
                memory_data = {}
    
    memory_data[question] = {"answer": answer, "trust": trust}
    
    with open(bot.MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, ensure_ascii=False, indent=2)
    
    flash("Memory entry updated successfully!", "success")
    return redirect(url_for('memory'))

@app.route('/stats')
def stats():
    """Render statistics page"""
    # Calculate statistics from history and memory
    history_data = []
    memory_data = {}
    
    if os.path.exists(bot.HISTORY_FILE):
        with open(bot.HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                history_data = json.load(f)
            except json.JSONDecodeError:
                history_data = []
    
    if os.path.exists(bot.MEMORY_FILE):
        with open(bot.MEMORY_FILE, "r", encoding="utf-8") as f:
            try:
                memory_data = json.load(f)
            except json.JSONDecodeError:
                memory_data = {}
    
    # Basic statistics
    total_interactions = len(history_data)
    total_memories = len(memory_data)
    
    # Interactions per day (last 7 days)
    interactions_by_day = {}
    today = date.today()
    for i in range(7):
        day = today - timedelta(days=i)
        interactions_by_day[day.isoformat()] = 0
    
    for entry in history_data:
        try:
            entry_time = datetime.fromisoformat(entry.get('time', ''))
            day = entry_time.date().isoformat()
            if day in interactions_by_day:
                interactions_by_day[day] += 1
        except ValueError:
            continue
    
    # Sort days in ascending order
    interactions_chart_data = []
    for day, count in sorted(interactions_by_day.items()):
        interactions_chart_data.append({
            'day': day,
            'count': count
        })
    
    return render_template(
        'stats.html', 
        total_interactions=total_interactions,
        total_memories=total_memories,
        interactions_chart_data=json.dumps(interactions_chart_data),
        now=datetime.now()
    )

@app.route('/api/bot_status')
def bot_status():
    """API endpoint to check if the bot is running"""
    return jsonify({"running": bot_running})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
