# MedBridge Developer Guide

This guide helps contributors run, understand, and extend the project.

## 1) Repository Structure

```text
.
├── app.py                     # Flask backend, routes, models, agent logic
├── services/
│   └── meralion_client.py     # MERaLiON STT client wrapper
├── static/
│   ├── index.html             # Main UI
│   ├── app.js                 # Frontend logic (voice, chat, dashboard)
│   └── styles.css
├── instance/
│   └── medbridge.db           # SQLite database file
├── healthhub_agent/           # Bridge service (FastAPI + Playwright)
├── HealthHub WebApp/          # React mock HealthHub portal (Vite)
└── requirements.txt
```

## 2) Local Setup

### Backend
```bash
pip install -r requirements.txt
python app.py
```

Flask runs on `http://localhost:5001`.

### Optional Services

#### HealthHub WebApp
```bash
cd "HealthHub WebApp"
npm install
npm run dev
```
Runs on `http://localhost:5173`.

#### HealthHub Agent Bridge
```bash
cd healthhub_agent
pip install -r requirements.txt
python server.py
```
Runs on `http://localhost:7001`.

## 3) Environment Variables

Create `.env` at project root:

```env
SECRET_KEY=your-secret
SEALION_API_KEY=your-sealion-key
MERALION_API_KEY=your-meralion-key
MERALION_BASE_URL=optional-custom-base-url
LLM_MODEL=optional-model-id
```

For Google TTS, use ADC login:
```bash
gcloud auth application-default login
```

## 4) Backend Architecture

- **Framework**: Flask + Flask-CORS + SQLAlchemy
- **LLM**: SEA-LION via OpenAI-compatible client
- **Speech**:
  - STT: MERaLiON (`/api/voice`)
  - TTS: Google Cloud (`/api/tts`)
- **Language Detection**: `/api/language/detect` (heuristic + LLM assist)
- **DB**: SQLite (`sqlite:///medbridge.db`)

## 5) Core Database Models

- `Patient`
- `Session`, `Message`
- `AgentSession`, `AgentMessage`
- `Appointment`
- `Medication`
- `FamilyMember`

## 6) Key API Endpoints

- `GET /api/languages`
- `POST /api/language/detect`
- `GET /api/voice/health`
- `POST /api/voice`
- `POST /api/tts`
- `POST /api/patients`, `GET /api/patients`
- `POST /api/sessions`, `POST /api/sessions/<id>/message`, `POST /api/sessions/<id>/complete`
- `POST /api/agent/start`, `POST /api/agent/sessions/<id>/message`
- `GET /api/appointments`, `GET /api/medications`, `GET/POST /api/family`, `GET /api/health-summary`

## 7) Frontend Notes

- Main app is a vanilla JS SPA in `static/app.js`.
- Voice behavior includes:
  - cloud TTS playback
  - browser TTS fallback
  - MERaLiON STT path
  - browser STT fallback
- My Health and Doctor Portal views are currently active in UI.

## 8) Development Tips

- Keep generated files out of commits (`node_modules`, `.pyc`, DB snapshots).
- If SQLite file is locked on Windows, stop Flask before stashing or resetting.
- Validate syntax quickly:
  - `python -m py_compile app.py services/meralion_client.py`
  - `node --check static/app.js`

## 9) Known Limitations

- MERaLiON depends on external network/DNS reliability.
- Browser STT fallback can be less accurate for mixed-language speech.
- Some advanced features in product vision (for example SMS caregiver notifications) are roadmap items.

