# 📚 StudyBot — WhatsApp Group Study Logger

## What it does
- Silently logs every member's study goals + progress
- Posts a clean daily summary at midnight
- No chatting — pure logging and organizing

---

## DEPLOY ON RAILWAY (from phone)

### Step 1 — Push to GitHub
1. Go to github.com on phone browser
2. Create new repository called "studybot"
3. Upload all 4 files: app.py, requirements.txt, Procfile, .env

### Step 2 — Deploy on Railway
1. Go to railway.app
2. New Project → Deploy from GitHub repo
3. Select "studybot"
4. Railway auto-detects Python and deploys
5. Go to Settings → Domains → Generate Domain
6. Copy your URL like: https://studybot-xxxx.railway.app

### Step 3 — Connect Twilio Webhook
1. Go to Twilio Console
2. Messaging → Try it out → WhatsApp Sandbox
3. Under "When a message comes in" paste:
   https://studybot-xxxx.railway.app/bot
4. Method: HTTP POST
5. Save

---

## ACTIVATE FOR EACH MEMBER
Every member must send this message to +14155238886:
```
join birth-sea
```
They get a confirmation from Twilio. After that they're connected.

---

## HOW MEMBERS LOG

### Set your name first (one time):
```
MYNAME: Neel
```

### Log with goal + progress:
```
Goal: Complete Normalisation
Done: Revised up to BCNF, 3NF pending
```

### Or just free text goal:
```
Revised OS deadlock chapter
```

### Multiple goals — send multiple messages:
```
Goal: Finish DBMS transactions
Done: Completed, all topics done
```
```
Goal: Solve 10 GATE PYQs
Done: Solved 6, 4 remaining
```

---

## DAILY SUMMARY

### Auto at midnight — set up cron:
Use cron-job.org (free):
1. Go to cron-job.org
2. New cronjob
3. URL: https://studybot-xxxx.railway.app/summary?to=whatsapp:+91YOURNUMBER
4. Schedule: 0 0 * * * (midnight daily)
5. Save

### Manual trigger anytime:
Open in browser:
https://studybot-xxxx.railway.app/summary?to=whatsapp:+91YOURNUMBER

### Preview in browser:
https://studybot-xxxx.railway.app/preview

---

## SUMMARY FORMAT
```
📚 DAILY LOG — 11 June 2026
────────────────────────────
👤 Neel
  • Complete Normalisation
    ↳ Revised up to BCNF, 3NF pending ⏳
  • Solve 10 GATE PYQs  
    ↳ Solved 6, 4 remaining ⏳

👤 Member 2
  • Finish OS Deadlock
    ↳ Completed ✅
────────────────────────────
Total logs today: 3
```

---

## STATUS DETECTION (automatic)
Bot auto-detects status from your "Done" text:
- Words like "complete/done/finished" → ✅
- Words like "pending/partial/remaining" → ⏳
- Anything else → 📝
