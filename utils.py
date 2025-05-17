import json
import os
import datetime
from collections import Counter

# File paths
MEMORY_FILE = "ai_memory.json"
HISTORY_FILE = "chat_history.json"

def get_memory_stats():
    """Get statistics about the bot's memory"""
    memory_data = {}
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            try:
                memory_data = json.load(f)
            except json.JSONDecodeError:
                memory_data = {}
    
    # Basic stats
    total_memories = len(memory_data)
    
    # Average answer length
    answer_lengths = []
    for question, data in memory_data.items():
        if isinstance(data, dict) and 'answer' in data:
            answer_lengths.append(len(data['answer']))
        elif isinstance(data, str):
            answer_lengths.append(len(data))
    
    avg_answer_length = sum(answer_lengths) / len(answer_lengths) if answer_lengths else 0
    
    # Count of trusted answers (trust = 1.0)
    trusted_answers = 0
    for question, data in memory_data.items():
        if isinstance(data, dict) and data.get('trust', 0) == 1.0:
            trusted_answers += 1
        elif isinstance(data, str):  # Legacy format assumed trust = 1.0
            trusted_answers += 1
    
    return {
        'total_memories': total_memories,
        'avg_answer_length': round(avg_answer_length, 1),
        'trusted_answers': trusted_answers
    }

def get_history_stats():
    """Get statistics about the chat history"""
    history_data = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                history_data = json.load(f)
            except json.JSONDecodeError:
                history_data = []
    
    # Basic stats
    total_interactions = len(history_data)
    
    # Interactions by day
    day_counter = Counter()
    for entry in history_data:
        try:
            entry_time = datetime.datetime.fromisoformat(entry.get('time', ''))
            day = entry_time.date().isoformat()
            day_counter[day] += 1
        except ValueError:
            continue
    
    # Most active days
    most_active_days = day_counter.most_common(5)
    
    # Unique users
    unique_users = set()
    for entry in history_data:
        user_id = entry.get('user_id')
        if user_id:
            unique_users.add(user_id)
    
    return {
        'total_interactions': total_interactions,
        'most_active_days': most_active_days,
        'unique_users': len(unique_users)
    }

def get_common_questions():
    """Get the most common questions from history"""
    history_data = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                history_data = json.load(f)
            except json.JSONDecodeError:
                history_data = []
    
    # Count questions
    question_counter = Counter()
    for entry in history_data:
        question = entry.get('user', '')
        if question:
            question_counter[question] += 1
    
    # Get most common questions
    common_questions = question_counter.most_common(10)
    
    return common_questions
