# MedBridge — Multilingual Healthcare Communication Platform

A healthcare tool that conducts **multilingual, dialect-aware** pre-consultation check-ins and post-consultation follow-ups. It translates medical information into culturally appropriate, easy-to-understand language for patients while generating concise, structured clinical summaries for clinicians.

## Features

- **13+ languages** with dialect/variant awareness (Spanish Mexican vs. Caribbean, Mandarin Simplified vs. Traditional, Arabic Egyptian vs. Levantine, etc.)
- **Pre-consultation check-ins**: gathers chief complaints, symptoms, medications, allergies, and red-flag screening in the patient's language
- **Post-consultation follow-ups**: reviews diagnosis, explains medications, uses teach-back to verify understanding, and discusses warning signs
- **Cultural adaptation**: adjusts communication style based on cultural context (family decision-making norms, dietary/religious considerations, naming conventions)
- **Dual summaries**: generates a structured clinical summary (in English) for the clinician AND a plain-language patient summary in the patient's preferred language
- **Clinician dashboard**: browse sessions, view clinical summaries, read full conversation transcripts, filter by type/status

## Architecture

```
┌────────────────────────┐     ┌──────────────────────────┐
│   Patient Portal       │────▶│  Flask API Server        │
│   (HTML/CSS/JS SPA)    │◀────│  - SQLite database       │
└────────────────────────┘     │  - OpenAI GPT-4o engine  │
                               └──────────────────────────┘
┌────────────────────────┐              │
│  Clinician Dashboard   │──────────────┘
│  (Same SPA, diff view) │
└────────────────────────┘
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your OpenAI API key

Create a `.env` file:

```
OPENAI_API_KEY=your-openai-api-key-here
SECRET_KEY=any-random-string-here
```

### 3. Run the server

```bash
python3 app.py
```

### 4. Open in browser

Navigate to **http://localhost:5000**

## Usage

### Patient Portal

1. Click **Patient Check-In** from the home page
2. Enter your name, select your preferred language and dialect
3. Optionally add cultural considerations (e.g., "Family makes decisions together")
4. Choose **Pre-Consultation Check-In** or **Post-Consultation Follow-Up**
5. Chat with MedBridge in your language — it will ask relevant medical questions
6. When done, click **Complete & Summarize** to get your visit summary

### Clinician Dashboard

1. Click **Clinician Dashboard** from the navigation
2. Browse all patient sessions in the sidebar (filter by type/status)
3. Click any session to see:
   - **Clinical Summary** — structured with Chief Complaint, HPI, Medications, Red Flags, Cultural Considerations, Adherence Risk
   - **Patient Summary** — the summary given to the patient in their language
   - **Full Conversation Transcript** — every message exchanged

## Supported Languages & Dialects

| Language | Dialects |
|----------|----------|
| English | General American, British, Australian, AAVE, Southern US |
| Spanish | Mexican, Caribbean, Central American, South American, Peninsular |
| Mandarin Chinese | Simplified/Mainland, Traditional/Taiwan, Cantonese-influenced |
| Arabic | Modern Standard, Egyptian, Levantine, Gulf, Maghrebi |
| Hindi | Standard Hindi, Hinglish, Bhojpuri-influenced |
| French | Metropolitan, Canadian/Québécois, West African, Haitian Creole-influenced |
| Portuguese | Brazilian, European, Mozambican |
| Vietnamese | Northern, Southern, Central |
| Korean | Standard/Seoul, Gyeongsang, Jeolla |
| Tagalog | Standard Filipino, Taglish |
| Russian | Standard, Ukrainian-influenced |
| Haitian Creole | Standard |
| Somali | Standard, Maay |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/languages` | List supported languages and dialects |
| POST | `/api/patients` | Register a new patient |
| GET | `/api/patients` | List all patients |
| GET | `/api/patients/<id>` | Get patient details |
| POST | `/api/sessions` | Start a new check-in or follow-up session |
| POST | `/api/sessions/<id>/message` | Send a chat message |
| POST | `/api/sessions/<id>/complete` | Complete session and generate summaries |
| GET | `/api/sessions/<id>` | Get full session details |
| GET | `/api/sessions` | List all sessions |
| POST | `/api/translate` | On-demand medical text translation |
