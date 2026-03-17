# MedBridge User Guide

This guide is for patients and clinic staff using the MedBridge web app.

## 1) Open the App

1. Start backend (`python app.py`)
2. Open browser at `http://localhost:5001`

You will see:
- **Home**
- **My Health**
- **Doctor Portal**

---

## 2) Patient Guide: My Health

### Start a Session
1. Click **My Health**
2. Enter your name
3. Choose language (or **Auto-detect from first message**)
4. Click start

### Talk to Aria
- Use the mic button to speak, or type in the chat box.
- Example intents:
  - "Book an appointment"
  - "Show my medications"
  - "Add my daughter as family member"
  - "Give me my health summary"

### Voice Mode
- If auto voice mode is ON, Aria will:
  1. speak response
  2. listen automatically
  3. send your next utterance

### Language Behavior
- In auto-detect mode, first utterance is used to select language/dialect.
- If MERaLiON is unavailable, app can fall back to browser STT.

### Dashboard
Click **Dashboard** in My Health to view:
- Upcoming appointments
- Medications
- Family members
- Summary cards

---

## 3) Doctor Guide: Doctor Portal

### View Sessions
1. Click **Doctor Portal**
2. Use filters (status/urgency) if needed
3. Select a session from the list

### Review Clinical Output
For each session, you can review:
- Patient details
- Clinical summary
- Transcript entries
- English translations where available

### Mark Urgency
- Use the urgency action in the session panel when needed.

---

## 4) Common Troubleshooting

### "No speech transcription appears"
- Confirm microphone permission is granted in browser
- Check if MERaLiON is reachable (`/api/voice/health`)
- If MERaLiON is down, use browser STT fallback

### "Voice sounds robotic"
- Confirm cloud TTS route is returning 200 (`POST /api/tts`)
- If cloud TTS fails, browser TTS fallback may sound less natural

### "Language detected incorrectly"
- Try a longer first utterance in auto-detect mode
- Ensure mic is clear and there is low background noise

