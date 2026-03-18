# MedBridge — Voice AI Healthcare Assistant

MedBridge is an AI-powered, voice-first healthcare platform built for Singapore's multilingual population. It combines a conversational health assistant (Aria) with real-time HealthHub browser automation and a Doctor Portal into a single web app.

## What It Does

### My Health — Aria (Agentic Voice AI)
Talk to Aria, MedBridge's AI health assistant, entirely by voice or text. Aria can:
- **Book appointments on HealthHub** — asks you one question at a time (hospital → department → date → time → reason), then automates the entire HealthHub booking form live in the right panel while you watch
- **View your appointments, medications, and lab reports** from the database
- **Answer health questions** and provide health summaries
- **Support family members** — manage dependants' health records

The right panel streams a live view of the Playwright-controlled Chrome browser as Aria fills in forms on HealthHub.

### Doctor Portal
Browse all patient sessions, view clinical summaries, and read full conversation transcripts.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│   MedBridge SPA  (http://localhost:5001)                │
│   ┌──────────────────┐  ┌──────────────────────────┐   │
│   │  Aria Chat (Left)│  │  HealthHub Live (Right)  │   │
│   │  Voice + Text UI │  │  Live screenshots via WS │   │
│   └────────┬─────────┘  └───────────┬──────────────┘   │
└────────────┼───────────────────────┼────────────────────┘
             │ REST API              │ WebSocket
             ▼                       ▼
┌─────────────────────┐   ┌─────────────────────────────┐
│  Flask Backend      │   │  HealthHub Agent Bridge     │
│  (port 5001)        │──▶│  FastAPI + Playwright       │
│  - SEA-LION LLM     │   │  (port 7001)                │
│  - Agentic loop     │   │  - Headed Chrome browser    │
│  - SQLite DB        │   │  - Full booking automation  │
│  - 11 tools         │   │  - Screenshot streaming     │
└─────────────────────┘   └──────────┬──────────────────┘
                                     │ Playwright controls
                                     ▼
                          ┌─────────────────────────┐
                          │  HealthHub              │
                          │  (Playwright-controlled) │
                          └─────────────────────────┘
```

**Key design decisions:**
- LLM (SEA-LION) is the reasoning brain — it decides when/what to book, not hardcoded scripts
- Playwright automation is a reliable tool the LLM calls, not a fragile vision-based agent
- WebSocket streams JPEG screenshots ~2 FPS so users watch automation happen live
- `asyncio.Lock()` serialises all browser actions — no concurrent automation
- Auto-recovery: if Chrome window is closed, bridge restarts it automatically

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla JS SPA, Web Speech API (STT/TTS) |
| Backend | Flask + SQLite (SQLAlchemy) |
| LLM | SEA-LION (`aisingapore/Qwen-SEA-LION-v4-32B-IT`) |
| Browser Automation | Playwright (async, headed Chromium) |
| Bridge Server | FastAPI + Uvicorn |

---

## Quick Start

### Prerequisites
- Python 3.11+

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
pip install -r healthhub_agent/requirements.txt
playwright install chromium
```

### 2. Set environment variables

Create a `.env` file in the project root:

```env
SEALION_API_KEY=your-sea-lion-api-key-here
SECRET_KEY=any-random-string
```

### 3. Start the HealthHub Agent Bridge

```bash
cd healthhub_agent
python3 server.py
# Runs on http://localhost:7001
# Opens a headed Chrome window automatically
```

### 4. Start MedBridge

```bash
# From project root
python3 app.py
# Runs on http://localhost:5001
```

### 5. Open in browser

Navigate to **http://localhost:5001**

---

## Usage

### Booking an Appointment via Aria

1. Click **My Health** in the top navigation
2. Enter your name and preferred language, click **Start with Aria**
3. Say or type: *"I want to book an appointment"*
4. Aria asks one question at a time:
   - Which hospital or polyclinic?
   - Which department?
   - What date?
   - What time?
   - Reason for visit?
5. Once all details are collected, Aria says *"Got it! Let me book that for you now."*
6. Watch the right panel — Playwright fills the entire HealthHub form automatically

### Viewing Health Information

Ask Aria things like:
- *"Show me my upcoming appointments"*
- *"What medications am I on?"*
- *"Give me a health summary"*

---

## Project Structure

```
ai_challenge/
├── app.py                    # Flask backend — all routes, DB models, agentic loop
├── requirements.txt
├── static/
│   ├── index.html            # Single-page app
│   ├── app.js                # All frontend JS (voice, chat, WebSocket, navigation)
│   └── styles.css            # Design system
├── healthhub_agent/          # Browser automation bridge
│   ├── server.py             # FastAPI server (port 7001)
│   ├── dispatcher.py         # Playwright singleton — booking automation
│   ├── requirements.txt
│   └── actions/              # Action registry (extensible)
└── instance/
    └── medbridge.db          # SQLite database
```

---

## Agentic Architecture

MedBridge uses a **tool-augmented agentic loop**:

```
User message
     │
     ▼
SEA-LION LLM  (run_agent loop, up to 6 iterations)
     │
     ├── Asks follow-up question → responds with text
     │
     └── Calls a tool:
           ├── book_on_healthhub(institution, specialty, date, time, reason)
           │     └── POST /api/booking/full → Playwright runs 12-step automation
           ├── view_healthhub(page)
           ├── get_appointments(patient_id)
           ├── get_medications(patient_id)
           ├── get_health_summary(patient_id)
           └── ... 11 tools total
```

The LLM autonomously decides when it has enough information to act. It reasons over the full conversation history and calls the right tool at the right time.

---

## Supported Languages

English, Mandarin Chinese, Malay, Tamil, Hindi, Arabic, Tagalog, Vietnamese, Korean, Japanese, French, Spanish, Portuguese — with dialect awareness (e.g. Singapore English vs. British English, Simplified vs. Traditional Chinese).

---

## API Reference

**MedBridge (port 5001):**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/languages` | List supported languages |
| POST | `/api/agent/start` | Start an Aria session |
| POST | `/api/agent/sessions/<id>/message` | Send message to Aria |
| GET | `/api/appointments?patient_id=` | List appointments |
| GET | `/api/medications?patient_id=` | List medications |
| GET | `/api/health-summary?patient_id=` | Full health overview |
| POST | `/api/sessions` | Start pre/post-consultation session |
| POST | `/api/sessions/<id>/message` | Chat message |
| GET | `/api/sessions` | List all sessions (doctor portal) |

**Bridge (port 7001):**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Browser ready status |
| POST | `/api/booking/full` | Run full HealthHub booking automation |
| POST | `/api/navigate` | Navigate HealthHub to a specific page |
| WS | `/ws` | Screenshot stream + action events |
