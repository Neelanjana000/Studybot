from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import json
import os
import re

app = Flask(__name__)

# Twilio credentials
ACCOUNT_SID = os.environ.get("TWILIO_SID", "AC369352bfdeb877d4dfdceb7af12ea9b6")
AUTH_TOKEN  = os.environ.get("TWILIO_TOKEN", "5d0641532638b0eefc4adf9b352cbda0")
SANDBOX_NUM = "whatsapp:+14155238886"

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# In-memory log store: { "YYYY-MM-DD": { "Name": [ {"goal":..,"done":..}, ... ] } }
logs = {}

def today():
    return datetime.now().strftime("%Y-%m-%d")

def display_date():
    return datetime.now().strftime("%d %B %Y")

def get_sender_name(from_number):
    """Use number as name — members can set nickname via 'MYNAME: Neel'"""
    return names.get(from_number, from_number.replace("whatsapp:+91","").replace("whatsapp:",""))

# Name registry: { number: name }
names = {}

def parse_message(body):
    """
    Accepts free text. Detects:
    - Name registration: MYNAME: Neel
    - Goal log: Goal: ... / Done: ...
    - Single line: anything else treated as goal with no done yet
    """
    body = body.strip()

    # Name registration
    if body.lower().startswith("myname:"):
        name = body.split(":", 1)[1].strip()
        return {"type": "name", "value": name}

    # Structured Goal + Done
    goal_match = re.search(r"goal[:\-\s]+(.+?)(?=done[:\-\s]|$)", body, re.IGNORECASE | re.DOTALL)
    done_match = re.search(r"done[:\-\s]+(.+)", body, re.IGNORECASE | re.DOTALL)

    if goal_match:
        goal = goal_match.group(1).strip().rstrip("\n")
        done = done_match.group(1).strip() if done_match else None
        return {"type": "log", "goal": goal, "done": done}

    # Free text — treat whole message as goal, no done yet
    return {"type": "log", "goal": body, "done": None}

def save_log(sender, goal, done):
    date = today()
    if date not in logs:
        logs[date] = {}
    name = get_sender_name(sender)
    if name not in logs[date]:
        logs[date][name] = []
    logs[date][name].append({"goal": goal, "done": done})

def build_summary(date=None):
    date = date or today()
    if date not in logs or not logs[date]:
        return f"📚 DAILY LOG — {display_date()}\n\nNo logs recorded today."

    lines = [f"📚 DAILY LOG — {display_date()}", "─" * 28]
    total = 0
    for name, entries in logs[date].items():
        lines.append(f"\n👤 {name}")
        for e in entries:
            goal = e["goal"]
            done = e["done"]
            if done:
                # Determine status emoji
                done_lower = done.lower()
                if any(w in done_lower for w in ["complete", "done", "finished", "all"]):
                    status = "✅"
                elif any(w in done_lower for w in ["pending", "partial", "half", "still", "remaining"]):
                    status = "⏳"
                else:
                    status = "📝"
                lines.append(f"  • {goal}")
                lines.append(f"    ↳ {done} {status}")
            else:
                lines.append(f"  • {goal} ⏳")
            total += 1

    lines.append("\n" + "─" * 28)
    lines.append(f"Total logs today: {total}")
    return "\n".join(lines)

@app.route("/bot", methods=["POST"])
def bot():
    sender = request.form.get("From")
    body   = request.form.get("Body", "").strip()
    group  = request.form.get("To")

    resp = MessagingResponse()

    # Ignore empty
    if not body:
        return str(resp)

    parsed = parse_message(body)

    if parsed["type"] == "name":
        names[sender] = parsed["value"]
        # Silent — no reply, just register
        return str(resp)

    if parsed["type"] == "log":
        save_log(sender, parsed["goal"], parsed["done"])
        # Silent — no reply, just log

    return str(resp)

@app.route("/summary", methods=["GET"])
def send_summary():
    """
    Call this endpoint at midnight via cron to post daily summary.
    Pass ?to=whatsapp:+91XXXXXXXXXX (group or individual number)
    """
    to = request.args.get("to", SANDBOX_NUM)
    summary = build_summary()

    client.messages.create(
        from_=SANDBOX_NUM,
        to=to,
        body=summary
    )
    return "Summary sent!", 200

@app.route("/preview", methods=["GET"])
def preview():
    """Preview today's summary in browser"""
    return build_summary().replace("\n", "<br>")

@app.route("/", methods=["GET"])
def index():
    return "StudyBot is running! ✅"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
