import os
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import telebot

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8033069276:AAFv1-kdQ68LjvLEgLHj3ZXd5ehMqyUXOYU")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6482440657"))
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@ReviewCashNews")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://YOUR-VERCEL-URL.vercel.app")

DB_PATH = "data.db"
PORT = int(os.getenv("PORT", 8080))

# ================== INIT ==================
app = Flask(__name__, static_folder="public", static_url_path="")
CORS(app)

bot = telebot.TeleBot(BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

# ================== DB ==================
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = db().cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        uid TEXT PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        role TEXT DEFAULT 'user',
        created_at TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        reward INTEGER,
        status TEXT DEFAULT 'active'
    )
    """)
    c.connection.commit()
    c.connection.close()

init_db()

# ================== HELPERS ==================
def is_subscribed(user_id: int) -> bool:
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False

def ensure_user(uid):
    c = db().cursor()
    c.execute("SELECT * FROM users WHERE uid=?", (uid,))
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (uid, created_at) VALUES (?,?)",
            (uid, datetime.utcnow().isoformat())
        )
        c.connection.commit()
    c.connection.close()

# ================== WEB ==================
@app.route("/")
def index():
    return send_from_directory("public", "index.html")

@app.route("/api/check-subscription", methods=["POST"])
def api_check_sub():
    uid = request.json.get("uid")
    if not uid:
        return jsonify(ok=False)

    return jsonify(ok=is_subscribed(int(uid)))

@app.route("/api/profile")
def api_profile():
    uid = request.args.get("uid")
    ensure_user(uid)
    c = db().cursor()
    c.execute("SELECT * FROM users WHERE uid=?", (uid,))
    user = dict(c.fetchone())
    c.connection.close()
    return jsonify(ok=True, user=user)

@app.route("/api/tasks")
def api_tasks():
    c = db().cursor()
    c.execute("SELECT * FROM tasks WHERE status='active'")
    tasks = [dict(x) for x in c.fetchall()]
    c.connection.close()
    return jsonify(ok=True, tasks=tasks)

# ================== BOT ==================
@bot.message_handler(commands=["start"])
def start(msg):
    uid = msg.from_user.id

    if not is_subscribed(uid):
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(
            telebot.types.InlineKeyboardButton(
                "📢 Подписаться",
                url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"
            )
        )
        bot.send_message(
            uid,
            "❌ Для использования бота нужно подписаться на канал",
            reply_markup=kb
        )
        return

    ensure_user(str(uid))

    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(
        telebot.types.InlineKeyboardButton(
            "🚀 Открыть ReviewCash",
            web_app=telebot.types.WebAppInfo(url=WEBAPP_URL)
        )
    )
    bot.send_message(uid, "✅ Добро пожаловать в ReviewCash", reply_markup=kb)

# ================== RUN ==================
if __name__ == "__main__":
    logging.info("Starting bot + backend")
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
