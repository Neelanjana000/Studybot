import sqlite3
import re
from datetime import date, datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

DB = "study_logs.db"
TOKEN = "8627106745:AAFCt-22D7k0cxJ1yuOKHtdJTPDhiANPuRc"

# ─── Database ────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        first_name TEXT,
        goal TEXT,
        done TEXT,
        hours REAL,
        log_date TEXT,
        chat_id INTEGER
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS goals(
        user_id INTEGER PRIMARY KEY,
        daily_goal REAL
    )""")
    conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect(DB)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_name(user):
    """Get display name from Telegram user object."""
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Unknown"

def parse_free_text(text):
    """
    Parse free text into goal + done + hours.
    Supports:
      /log 2 DBMS                          → hours=2, goal=DBMS
      Goal: Complete DBMS\nDone: Finished  → goal+done
      Just free text                        → treated as goal
    """
    text = text.strip()

    # Try Goal:/Done: format
    goal_match = re.search(r"goal[:\-\s]+(.+?)(?=done[:\-\s]|$)", text, re.IGNORECASE | re.DOTALL)
    done_match = re.search(r"done[:\-\s]+(.+)", text, re.IGNORECASE | re.DOTALL)

    if goal_match:
        goal = goal_match.group(1).strip()
        done = done_match.group(1).strip() if done_match else None
        return goal, done, None

    # Free text → treat as goal
    return text, None, None

def status_emoji(done_text):
    if not done_text:
        return "⏳"
    d = done_text.lower()
    if any(w in d for w in ["complete", "done", "finished", "all", "full"]):
        return "✅"
    if any(w in d for w in ["pending", "partial", "half", "still", "remaining", "not"]):
        return "⏳"
    return "📝"

def today_str():
    return str(date.today())

def display_date():
    return datetime.now().strftime("%d %B %Y")

# ─── Commands ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *Study Log Bot*\n\n"
        "Log your study in any format:\n\n"
        "*Free text:*\n"
        "Goal: Complete Normalisation\n"
        "Done: Revised BCNF, 3NF pending\n\n"
        "*Or with hours:*\n"
        "`/log 2 DBMS`\n\n"
        "*Commands:*\n"
        "/today — Your logs today\n"
        "/all — Everyone's logs today\n"
        "/week — Your weekly hours\n"
        "/goal <hours> — Set daily goal\n"
        "/progress — Today's progress\n"
        "/streak — Your study streak\n"
        "/summary — Full group summary",
        parse_mode="Markdown"
    )

async def log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /log <hours> <subject>"""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /log <hours> <subject>\nExample: /log 2 DBMS")
        return
    try:
        hours = float(context.args[0])
    except ValueError:
        await update.message.reply_text("First argument must be hours. Example: /log 2 DBMS")
        return

    subject = " ".join(context.args[1:])
    user = update.effective_user
    chat_id = update.effective_chat.id

    conn = get_conn()
    conn.execute(
        "INSERT INTO logs(user_id,username,first_name,goal,done,hours,log_date,chat_id) VALUES(?,?,?,?,?,?,?,?)",
        (user.id, user.username, user.first_name, subject, None, hours, today_str(), chat_id)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Logged: {subject} — {hours}h")

async def free_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free text Goal:/Done: format in groups."""
    text = update.message.text
    if not text or text.startswith("/"):
        return

    # Only process if it looks like a study log
    has_goal = bool(re.search(r"goal[:\-\s]", text, re.IGNORECASE))
    has_done = bool(re.search(r"done[:\-\s]", text, re.IGNORECASE))

    if not (has_goal or has_done):
        return  # Ignore normal conversation

    goal, done, _ = parse_free_text(text)
    user = update.effective_user
    chat_id = update.effective_chat.id

    conn = get_conn()
    conn.execute(
        "INSERT INTO logs(user_id,username,first_name,goal,done,hours,log_date,chat_id) VALUES(?,?,?,?,?,?,?,?)",
        (user.id, user.username, user.first_name, goal, done, None, today_str(), chat_id)
    )
    conn.commit()
    conn.close()
    # Silent — no reply in group

async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current user's logs today."""
    uid = update.effective_user.id
    conn = get_conn()
    rows = conn.execute(
        "SELECT goal, done, hours FROM logs WHERE user_id=? AND log_date=?",
        (uid, today_str())
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No study logged today. Start with:\nGoal: <your goal>\nDone: <progress>")
        return

    name = get_name(update.effective_user)
    text = f"📚 *{name}'s Study — {display_date()}*\n\n"
    total_h = 0
    for goal, done, hours in rows:
        if hours:
            text += f"• {goal}: {hours}h\n"
            total_h += hours
        else:
            emoji = status_emoji(done)
            text += f"• {goal}\n"
            if done:
                text += f"  ↳ {done} {emoji}\n"
    if total_h > 0:
        text += f"\n⏱ Total: {total_h}h"

    await update.message.reply_text(text, parse_mode="Markdown")

async def all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show everyone's logs today in this chat."""
    chat_id = update.effective_chat.id
    conn = get_conn()
    rows = conn.execute(
        "SELECT user_id, first_name, username, goal, done, hours FROM logs WHERE log_date=? AND chat_id=? ORDER BY user_id",
        (today_str(), chat_id)
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No study logs today yet!")
        return

    # Group by user
    members = {}
    for uid, fname, uname, goal, done, hours in rows:
        name = f"@{uname}" if uname else (fname or str(uid))
        if name not in members:
            members[name] = []
        members[name].append((goal, done, hours))

    text = f"📚 *Group Study — {display_date()}*\n{'─'*25}\n"
    for name, entries in members.items():
        text += f"\n👤 *{name}*\n"
        for goal, done, hours in entries:
            if hours:
                text += f"  • {goal}: {hours}h\n"
            else:
                emoji = status_emoji(done)
                text += f"  • {goal}\n"
                if done:
                    text += f"    ↳ {done} {emoji}\n"
    text += f"\n{'─'*25}\n👥 {len(members)} member(s) logged today"

    await update.message.reply_text(text, parse_mode="Markdown")

async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for /all"""
    await all_cmd(update, context)

async def week_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    start_day = str(date.today() - timedelta(days=6))
    conn = get_conn()
    total = conn.execute(
        "SELECT SUM(hours) FROM logs WHERE user_id=? AND log_date>=? AND hours IS NOT NULL",
        (uid, start_day)
    ).fetchone()[0] or 0
    days = conn.execute(
        "SELECT COUNT(DISTINCT log_date) FROM logs WHERE user_id=? AND log_date>=?",
        (uid, start_day)
    ).fetchone()[0] or 0
    conn.close()
    await update.message.reply_text(f"📈 *Last 7 days*\nHours: {total}h\nDays active: {days}/7", parse_mode="Markdown")

async def goal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /goal <hours>\nExample: /goal 8")
        return
    try:
        target = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Please enter a number. Example: /goal 8")
        return
    uid = update.effective_user.id
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO goals(user_id,daily_goal) VALUES(?,?)", (uid, target))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🎯 Daily goal set to {target}h")

async def progress_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = get_conn()
    row = conn.execute("SELECT daily_goal FROM goals WHERE user_id=?", (uid,)).fetchone()
    studied = conn.execute(
        "SELECT SUM(hours) FROM logs WHERE user_id=? AND log_date=? AND hours IS NOT NULL",
        (uid, today_str())
    ).fetchone()[0] or 0
    conn.close()

    if not row:
        await update.message.reply_text("Set a goal first: /goal <hours>")
        return

    g = row[0]
    pct = (studied / g * 100) if g else 0
    bar_filled = int(pct / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)
    await update.message.reply_text(
        f"🎯 *Progress Today*\n{bar}\n{studied}/{g}h ({pct:.1f}%)",
        parse_mode="Markdown"
    )

async def streak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = get_conn()
    count = 0
    day = date.today()
    while True:
        has = conn.execute(
            "SELECT COUNT(*) FROM logs WHERE user_id=? AND log_date=?",
            (uid, str(day))
        ).fetchone()[0]
        if has:
            count += 1
            day -= timedelta(days=1)
        else:
            break
    conn.close()

    if count == 0:
        msg = "No streak yet — log today to start! 🚀"
    elif count < 3:
        msg = f"🔥 {count} day streak — keep going!"
    elif count < 7:
        msg = f"🔥🔥 {count} day streak — on fire!"
    else:
        msg = f"⚡ {count} day streak — UNSTOPPABLE!"

    await update.message.reply_text(msg)

# ─── Midnight Summary Job ─────────────────────────────────────────────────────

async def midnight_summary(context):
    """Auto-post daily summary to all active chats at midnight."""
    conn = get_conn()
    # Get all chats that had activity today
    chats = conn.execute(
        "SELECT DISTINCT chat_id FROM logs WHERE log_date=?",
        (today_str(),)
    ).fetchall()

    for (chat_id,) in chats:
        rows = conn.execute(
            "SELECT user_id, first_name, username, goal, done, hours FROM logs WHERE log_date=? AND chat_id=? ORDER BY user_id",
            (today_str(), chat_id)
        ).fetchall()

        if not rows:
            continue

        members = {}
        for uid, fname, uname, goal, done, hours in rows:
            name = f"@{uname}" if uname else (fname or str(uid))
            if name not in members:
                members[name] = []
            members[name].append((goal, done, hours))

        text = f"📚 *DAILY LOG — {display_date()}*\n{'─'*25}\n"
        for name, entries in members.items():
            text += f"\n👤 *{name}*\n"
            for goal, done, hours in entries:
                if hours:
                    text += f"  • {goal}: {hours}h\n"
                else:
                    emoji = status_emoji(done)
                    text += f"  • {goal}\n"
                    if done:
                        text += f"    ↳ {done} {emoji}\n"
        text += f"\n{'─'*25}\n👥 {len(members)} member(s) logged today\n\n_New day — new goals! 💪_"

        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to send summary to {chat_id}: {e}")

    conn.close()

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("log", log_command))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("all", all_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("week", week_cmd))
    app.add_handler(CommandHandler("goal", goal_cmd))
    app.add_handler(CommandHandler("progress", progress_cmd))
    app.add_handler(CommandHandler("streak", streak_cmd))

    # Free text handler (Goal:/Done: format)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_log))

    # Midnight summary — runs at 00:00 IST (18:30 UTC)
    app.job_queue.run_daily(
        midnight_summary,
        time=datetime.strptime("18:30", "%H:%M").time(),
        name="midnight_summary"
    )

    print("StudyBot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
