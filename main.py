import os
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import telebot

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6482440657"))
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@ReviewCashNews")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://YOUR-VERCEL-URL.vercel.app")

DB_PATH = "data.db"
PORT = int(os.getenv("PORT", 8000))

# ================== INIT ==================
app = Flask(__name__, static_folder="public", static_url_path="")
CORS(app)

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
logging.basicConfig(level=logging.INFO)

# ================== DB ==================
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    c = conn.cursor()

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

    conn.commit()
    conn.close()

init_db()

# ================== HELPERS ==================
def is_subscribed(user_id: int) -> bool:
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logging.warning(f"Subscription check failed: {e}")
        return False

def ensure_user(uid):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT uid FROM users WHERE uid=?", (uid,))
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (uid, created_at) VALUES (?, ?)",
            (uid, datetime.utcnow().isoformat())
        )
        conn.commit()
    conn.close()

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
    if not uid:
        return jsonify(ok=False)

    ensure_user(uid)
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE uid=?", (uid,))
    user = dict(c.fetchone())
    conn.close()

    return jsonify(ok=True, user=user)

@app.route("/api/tasks")
def api_tasks():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE status='active'")
    tasks = [dict(x) for x in c.fetchall()]
    conn.close()
    return jsonify(ok=True, tasks=tasks)

# ================== TELEGRAM WEBHOOK ==================
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK"

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
    logging.info("Starting Flask + Telegram webhook")

    bot.remove_webhook()
    bot.set_webhook(url=f"https://YOUR-PUBLIC-URL/webhook/{BOT_TOKEN}")

    app.run(host="0.0.0.0", port=PORT)
