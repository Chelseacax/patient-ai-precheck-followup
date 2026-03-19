# MedBridge — Voice AI Healthcare Assistant

MedBridge is an AI-powered, voice-first healthcare platform built for Singapore's multilingual population. It combines a conversational health assistant (Aria) with real-time HealthHub browser automation and a Doctor Portal into a single web app.

## What It Does

### My Health — Aria (Agentic Voice AI)
Talk to Aria, MedBridge's AI health assistant, entirely by voice or text. Aria can:
- **Book appointments on HealthHub** — collects your symptoms one question at a time, then navigates the live HealthHub portal interactively, reading real options from the page (available hospitals, services, dates, timeslots) before confirming with you
- **View your appointments, medications, and lab reports** from the database
- **Answer health questions** and provide health summaries
- **Support family members** — manage dependants' health records

The right panel streams a live view of the Playwright-controlled Chrome browser as Aria navigates HealthHub.

### Doctor Portal
Browse all patient appointment bookings and consultation sessions. Each appointment includes a structured symptom summary collected by Aria before booking — chief complaint, duration, severity, and associated symptoms.

- **Appointments tab** — all bookings made via Aria with full symptom summaries
- **Consultations tab** — voice check-in sessions with clinical summaries and bilingual transcripts

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
│  - OpenRouter LLM   │   │  (port 7001)                │
│  - Agentic loop     │   │  - Headed Chrome browser    │
│  - SQLite DB        │   │  - Interactive navigation   │
│  - 13 tools         │   │  - Screenshot streaming     │
└─────────────────────┘   └──────────┬──────────────────┘
                                     │ Playwright controls
                                     ▼
                          ┌─────────────────────────┐
                          │  HealthHub              │
                          │  (Playwright-controlled) │
                          └─────────────────────────┘
```

**Key design decisions:**
- LLM (OpenRouter / GPT-4o) is the reasoning brain — reads the live page and decides what to click
- Aria follows what is actually on screen, not hardcoded scripts — real options are read and presented to the user
- Symptom collection happens before every booking — structured summary saved to DB for doctors
- WebSocket streams JPEG screenshots ~2 FPS so users watch navigation happen live
- `asyncio.Lock()` serialises all browser actions — no concurrent automation
- Auto-recovery: if Chrome window is closed, bridge restarts it automatically

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla JS SPA, Web Speech API (STT/TTS) |
| Backend | Flask + SQLite (SQLAlchemy) |
| LLM | OpenRouter (`openai/gpt-4o`) with SEA-LION / Groq fallback |
| TTS | Google Cloud TTS (female voice, multilingual) |
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
OPENROUTER_API_KEY=your-openrouter-api-key
LLM_MODEL=openai/gpt-4o
GOOGLE_TTS_API_KEY=your-google-tts-api-key
SECRET_KEY=any-random-string

# Optional fallbacks
SEALION_API_KEY=your-sea-lion-api-key
GROQ_API_KEY=your-groq-api-key
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
4. Aria collects information in two phases:

   **Phase A — Before navigating (chat):**
   - Which hospital or polyclinic?
   - What is your main concern today?
   - How long have you had this?
   - How would you rate it — mild, moderate, or severe?
   - Any other symptoms?

   **Phase B — On HealthHub (interactive):**
   - Aria navigates to the appointments page
   - Reads available services, locations, dates, and timeslots from the live page
   - Presents real options to you and clicks your selections
   - Shows a booking summary and asks for your confirmation before submitting

5. Watch the right panel as Aria navigates HealthHub in real time

### Viewing Health Information

Ask Aria things like:
- *"Show me my upcoming appointments"*
- *"What medications am I on?"*
- *"Give me a health summary"*

### Doctor Portal

Click **Doctor Portal** in the top navigation to:
- **Appointments tab** — view all appointments booked via Aria, with the symptom summary collected before booking
- **Consultations tab** — view patient voice check-in sessions, clinical summaries, and bilingual transcripts

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
│   ├── dispatcher.py         # Playwright singleton — HealthHub navigation
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
LLM (OpenRouter/GPT-4o)  (run_agent loop, up to 12 iterations)
     │
     ├── Asks symptom questions one at a time → responds with text
     │
     └── Calls a tool:
           ├── view_healthhub(page)          → navigate browser to HealthHub page
           ├── interact_with_screen(...)     → read_page / click_text / scroll
           ├── get_appointments(patient_id)
           ├── get_medications(patient_id)
           ├── book_appointment(...)         → save booking to DB with symptom summary
           ├── get_health_summary(patient_id)
           └── ... 13 tools total
```

The LLM reads the live browser screen after every interaction and decides the next action based on what it sees — no hardcoded click sequences.

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
| GET | `/api/doctor/appointments` | All appointments with symptom summaries (Doctor Portal) |
| GET | `/api/sessions` | List consultation sessions (Doctor Portal) |
| GET | `/api/sessions/<id>` | Session detail with transcript |

**Bridge (port 7001):**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Browser ready status |
| POST | `/api/navigate` | Navigate HealthHub to a specific page |
| POST | `/api/browser/action` | Execute a browser action (click, scroll, read) |
| GET | `/api/browser/state` | Current screenshot + URL |
| WS | `/ws` | Screenshot stream + action events |
