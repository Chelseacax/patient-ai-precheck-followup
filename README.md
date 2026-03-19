# MedBridge — Voice AI Healthcare Assistant

MedBridge is an AI-powered, voice-first healthcare platform built for Singapore's multilingual population. It combines a conversational health assistant (Aria) with real-time HealthHub browser automation and a Doctor Portal into a single web app.

---

## What It Does

### My Health — Aria (Agentic Voice AI)
Talk to Aria, MedBridge's AI health assistant, by voice or text in any supported language. Aria can:
- **Book appointments on HealthHub** — collects symptoms one question at a time, then navigates the live HealthHub portal interactively, reads real options from the page (services, locations, dates, timeslots), and confirms with you before submitting
- **View appointments, medications, and health records** from the database
- **Answer health questions** and provide full health summaries
- **Manage family members** — handle dependants' health records

The right panel streams a live view of the Playwright-controlled Chrome browser as Aria navigates HealthHub in real time.

### Doctor Portal
Browse all patient appointments and consultation sessions with structured data collected by Aria before each booking.

- **Appointments tab** — all bookings with symptom summaries (chief complaint, duration, severity, associated symptoms)
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
│  - LLM (see below)  │   │  (port 7001)                │
│  - Agentic loop     │   │  - Headed Chrome browser    │
│  - SQLite DB        │   │  - Interactive navigation   │
│  - 13 tools         │   │  - Screenshot streaming     │
└─────────────────────┘   └──────────┬──────────────────┘
                                     │ Playwright controls
                                     ▼
                          ┌─────────────────────────┐
                          │  live HealthHub.sg       │
                          │  (eservices.healthhub.sg)│
                          └─────────────────────────┘
```

**Key design decisions:**
- LLM is the reasoning brain — reads the live page after every click and decides the next action
- No hardcoded click sequences — real options are read from the page and presented to the user
- Symptom collection happens before every booking — structured summary saved to DB for doctors
- WebSocket streams JPEG screenshots at ~2 FPS so users watch navigation happen live
- `asyncio.Lock()` serialises all browser actions — no concurrent automation
- Exact-match element targeting — clicking "No" always targets the exact button, never a button that merely contains the word "no"
- Auto-recovery: if the Chrome window is closed, the bridge restarts it automatically

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla JS SPA, Web Speech API (STT/TTS) |
| Backend | Flask + SQLite (SQLAlchemy) |
| LLM | OpenRouter (`openai/gpt-4o`, vision) → Groq (`llama-3.3-70b`) → SEA-LION → OpenAI |
| Speech-to-Text | MeRaLiON by IMDA (multilingual, Singapore-optimised) |
| Text-to-Speech | Google Cloud TTS (multilingual, female voice) |
| Browser Automation | Playwright (async, headed Chromium) |
| Bridge Server | FastAPI + Uvicorn |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Chromium (installed via Playwright)

### 1. Install dependencies

```bash
pip install -r requirements.txt
pip install -r healthhub_agent/requirements.txt
playwright install chromium
```

### 2. Configure environment variables

Create a `.env` file in the project root. You only need **one** LLM key — MedBridge picks the best available provider automatically:

```env
# LLM — provide at least one (OpenRouter recommended for vision support)
OPENROUTER_API_KEY=your-openrouter-api-key   # best: GPT-4o with live screenshots
GROQ_API_KEY=your-groq-api-key               # fallback: llama-3.3-70b, no vision
SEALION_API_KEY=your-sea-lion-api-key        # fallback: SEA-LION, no vision
OPENAI_API_KEY=your-openai-api-key           # fallback: GPT-4o direct

# Optional: override the OpenRouter model
LLM_MODEL=openai/gpt-4o

# Speech
GOOGLE_TTS_API_KEY=your-google-tts-api-key
MERALION_API_KEY=your-meralion-api-key

SECRET_KEY=any-random-string
```

### 3. Start everything (macOS)

```bash
./run_all.sh
```

This opens two Terminal windows (HealthHub bridge on :7001, Flask on :5001) and launches the app in your browser.

### Or start manually

```bash
# Terminal 1 — HealthHub Agent Bridge
cd healthhub_agent
python3 server.py          # opens headed Chrome on :7001

# Terminal 2 — MedBridge Flask app
python3 app.py             # runs on :5001
```

### 4. Open the app

Navigate to **http://localhost:5001**

> **First use:** The Chrome window will open on HealthHub. When Aria navigates to a page requiring login, it will prompt you to scan the Singpass QR code with your Singpass app.

---

## Usage

### Booking an Appointment via Aria

1. Click **My Health** in the top navigation
2. Enter your name and preferred language, click **Start with Aria**
3. Say or type: *"I want to book a polyclinic appointment"*
4. Aria works in two phases:

   **Phase A — Symptom collection (chat only):**
   - Which hospital or polyclinic?
   - What is your main concern today?
   - How long have you had this?
   - How would you rate it — mild, moderate, or severe?
   - Any other symptoms?

   **Phase B — Live HealthHub navigation:**
   - Aria navigates to the HealthHub appointments page
   - Reads available services, locations, and timeslots from the live page
   - Handles symptom screening forms automatically
   - Presents a booking summary and asks for confirmation before submitting

5. Watch the right panel as Aria navigates HealthHub in real time

### Viewing Health Information

Ask Aria things like:
- *"Show me my upcoming appointments"*
- *"What medications am I on?"*
- *"Give me a full health summary"*

### Doctor Portal

Click **Doctor Portal** to:
- **Appointments tab** — all Aria-booked appointments with full symptom summaries
- **Consultations tab** — voice check-in sessions with clinical summaries and transcripts

---

## Project Structure

```
ai_challenge/
├── app.py                    # Flask app factory + DB migration
├── models.py                 # SQLAlchemy models
├── extensions.py             # Shared db singleton
├── requirements.txt
├── run_all.sh                # One-command startup (macOS)
├── kill_all.sh               # Stop all services
│
├── agent/                    # Agentic loop
│   ├── loop.py               # LLM → tool calls → results → LLM (up to 20 iterations)
│   ├── prompts.py            # Aria system prompt (booking flow, rules, recovery)
│   ├── tools.py              # 13 OpenAI function-calling tool schemas
│   ├── dispatch.py           # Tool router
│   └── bridge.py             # HTTP client to healthhub_agent bridge
│
├── llm/                      # LLM provider abstraction
│   ├── provider.py           # Auto-select: OpenRouter → Groq → SEA-LION → OpenAI
│   └── client.py             # Unified chat completion call
│
├── routes/                   # Flask blueprints
│   ├── agent.py              # /api/agent/* (Aria sessions)
│   ├── sessions.py           # /api/sessions/* (consultations)
│   ├── patients.py           # /api/patients/*
│   ├── health.py             # /api/appointments, /api/medications, /api/health-summary
│   ├── voice.py              # /api/voice/transcribe (MeRaLiON STT)
│   ├── config.py             # /api/config (LLM key management)
│   ├── languages.py          # /api/languages
│   └── frontend.py           # Serve static SPA
│
├── services/
│   └── meralion_client.py    # MeRaLiON speech-to-text client
│
├── language/
│   ├── config.py             # 13 supported languages + dialects
│   └── detection.py          # Language detection helper
│
├── data/
│   └── doctors.py            # Mock doctor/slot data
│
├── static/
│   ├── index.html            # Single-page app
│   ├── app.js                # Voice, chat, WebSocket, navigation
│   └── styles.css            # Design system
│
├── healthhub_agent/          # Browser automation bridge (port 7001)
│   ├── server.py             # FastAPI: /api/browser/action, /api/status, /ws
│   ├── dispatcher.py         # Playwright singleton + modal dismissal
│   ├── requirements.txt
│   ├── actions/              # Action registry (REGISTRY dict)
│   │   ├── base.py
│   │   ├── navigation.py
│   │   ├── appointments.py
│   │   ├── medications.py
│   │   └── health_records.py
│   └── frontend/             # Bridge monitoring panel (served at :7001/)
│
└── instance/
    └── medbridge.db          # SQLite database
```

---

## Agentic Architecture

MedBridge uses a **tool-augmented agentic loop** (up to 20 iterations per message):

```
User message
     │
     ▼
LLM (resolves via provider priority)
     │
     ├── Asks symptom questions one at a time → returns text
     │
     └── Calls a tool:
           ├── view_healthhub(page)              → navigate browser
           ├── interact_with_screen(action, ...) → read_page / click_text / scroll / clear_modals
           ├── get_appointments(patient_id)
           ├── schedule_appointment(...)          → save to DB with symptom summary
           ├── get_medications(patient_id)
           ├── get_health_summary(patient_id)
           ├── add_family_member(...)
           └── ... 13 tools total
```

The LLM reads a live screenshot after every browser interaction and decides the next step based on what it sees — no hardcoded click sequences.

**Browser safety rules enforced at code level:**
- Header/footer elements (Sign up now, Log out, Inbox) excluded from `read_page` results
- `click_text` uses exact ARIA-role matching before falling back to partial match
- Ant Design modals auto-detected and dismissed after every click
- Newsletter/subscription popups cleared via `clear_modals` before each form step

---

## Supported Languages

English, Mandarin Chinese, Malay, Tamil, Hindi, Arabic, Tagalog, Vietnamese, Korean, Japanese, French, Spanish, Portuguese — with dialect awareness (Singapore English, Singlish, Simplified vs. Traditional Chinese, etc.).

---

## API Reference

**MedBridge (port 5001):**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/languages` | List supported languages |
| POST | `/api/agent/start` | Start an Aria session |
| POST | `/api/agent/sessions/<id>/message` | Send message to Aria |
| GET | `/api/agent/sessions/<id>` | Retrieve session history |
| GET | `/api/appointments?patient_id=` | List appointments |
| GET | `/api/medications?patient_id=` | List active medications |
| GET | `/api/health-summary?patient_id=` | Full health overview |
| GET | `/api/doctor/appointments` | All appointments with symptom summaries |
| GET | `/api/sessions` | Consultation sessions (Doctor Portal) |
| GET | `/api/sessions/<id>` | Session detail with transcript |
| POST | `/api/voice/transcribe` | Transcribe audio via MeRaLiON |

**HealthHub Bridge (port 7001):**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Browser ready status + current URL |
| POST | `/api/browser/action` | Execute browser action (read_page / click_text / scroll / clear_modals / navigate) |
| GET | `/api/browser/state` | Current screenshot (base64 JPEG) + URL |
| WS | `/ws` | Live screenshot stream + action events |
