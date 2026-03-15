/* ==========================================================================
   MedBridge — Frontend Application Logic
   Voice AI Pre-Consultation Check-In + Doctor Portal
   ========================================================================== */

const API = '';  // Same origin
const AUTO_DETECT_VALUE = '__auto_detect__';

// ---------------------------------------------------------------------------
// Speech language mapping (our language code → BCP 47 for Web Speech API)
// ---------------------------------------------------------------------------

const SPEECH_LANG_MAP = {
    'en':           'en-SG',
    'zh':           'zh-CN',
    'ms':           'ms-MY',
    'ta':           'ta-SG',
    'zh-cantonese': 'yue-HK',
    'nan':          'nan-TW',
    'hi':           'hi-IN',
    'tl':           'fil-PH',
    'vi':           'vi-VN',
    'th':           'th-TH',
    'id':           'id-ID',
    'my':           'my-MM',
    'bn':           'bn-BD',
    'km':           'km-KH',
};

const DIALECT_SPEECH_LANG_MAP = {
    'singlish': 'en-SG',
    'standard singapore english': 'en-SG',
    '新加坡华语 (singapore mandarin)': 'zh-SG',
    '标准普通话 (standard mandarin)': 'zh-CN',
    '新加坡广东话 (singapore cantonese)': 'yue-SG',
    '香港广东话 (hong kong cantonese)': 'yue-HK',
    'singapore hokkien': 'nan-SG',
    'taiwanese hokkien': 'nan-TW',
};

function resolveSpeechLang(code, dialect = '') {
    const key = (dialect || '').trim().toLowerCase();
    if (key && DIALECT_SPEECH_LANG_MAP[key]) {
        return DIALECT_SPEECH_LANG_MAP[key];
    }
    return SPEECH_LANG_MAP[code] || 'en-SG';
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let state = {
    languages: {},
    currentView: 'home',
};

let useMeralionStt = false;

// Voice check-in state
let checkinState = {
    patientId: null,
    sessionId: null,
    langCode: 'en',       // BCP-47 base code
    langName: 'English',
    dialect: '',
    isAutoMode: true,     // auto speak→listen→send loop
    isSpeaking: false,
    isListening: false,
    pendingLanguageDetect: false,
};

let checkinRec = null;        // active SpeechRecognition for check-in
let checkinUtterance = null;  // active TTS utterance for check-in
let checkinAudio = null;      // active cloud TTS audio element
let checkinMediaStream = null;
let checkinChunks = [];
let checkinStopTimer = null;

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function navigateTo(view) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`view-${view}`).classList.add('active');
    document.querySelectorAll('.nav-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.view === view);
    });
    state.currentView = view;

    if (view === 'doctor') loadSessions();
    if (view === 'checkin') showCheckinStep('checkin-setup');
    if (view === 'agent') { showAgentStep('agent-setup'); _hhConnectWS(); }

    stopCheckinSpeaking();
    stopCheckinVoice();
    stopAgentSpeaking();
    stopAgentVoice();
}

function showCheckinStep(stepId) {
    document.querySelectorAll('.checkin-step').forEach(s => s.classList.remove('active'));
    document.getElementById(stepId).classList.add('active');
}

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

async function init() {
    try {
        const res = await fetch(`${API}/api/languages`);
        state.languages = await res.json();
        populateCheckinLanguageDropdown();
        populateAgentLanguageDropdown();
    } catch (e) {
        console.error('Failed to load languages', e);
    }
    checkApiKey();
    checkMeralionHealth();
}

async function checkMeralionHealth() {
    try {
        const res = await fetch(`${API}/api/voice/health`);
        const data = await res.json();
        useMeralionStt = !!data.meralion_available;
        console.log(`MERaLiON STT: ${useMeralionStt ? 'available' : 'unavailable, using browser STT'}`);
    } catch (e) {
        useMeralionStt = false;
        console.warn('MERaLiON health check failed, using browser STT', e);
    }
}

async function checkApiKey() {
    try {
        const res = await fetch(`${API}/api/config/status`);
        const data = await res.json();
        const banner = document.getElementById('api-key-banner');
        if (!data.api_key_set || data.api_key_valid === false) {
            banner.classList.remove('hidden');
            if (data.api_key_set && data.api_key_valid === false) {
                banner.querySelector('span').innerHTML =
                    '<strong>Your API key is invalid or expired.</strong> Please enter a valid OpenAI (sk-...) or Groq (gsk_...) API key.';
            }
        } else {
            banner.classList.add('hidden');
        }
    } catch (e) {
        console.error('Failed to check API key status', e);
    }
}

async function saveApiKey() {
    const input = document.getElementById('api-key-input');
    const key = input.value.trim();
    if (!key) { alert('Please enter an API key (OpenAI sk-... or Groq gsk_...).'); return; }

    input.disabled = true;
    try {
        const res = await fetch(`${API}/api/config/apikey`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: key }),
        });
        const data = await res.json();
        if (res.ok) {
            document.getElementById('api-key-banner').classList.add('hidden');
            input.value = '';
        } else {
            alert(`Failed to save: ${data.error}`);
        }
    } catch (e) {
        alert('Network error while saving API key.');
    }
    input.disabled = false;
}

function dismissBanner() {
    document.getElementById('api-key-banner').classList.add('hidden');
}

// ---------------------------------------------------------------------------
// Check-In — Language Dropdowns
// ---------------------------------------------------------------------------

function populateCheckinLanguageDropdown() {
    const sel = document.getElementById('checkin-language');
    if (!sel) return;
    sel.innerHTML = '';

    const auto = document.createElement('option');
    auto.value = AUTO_DETECT_VALUE;
    auto.textContent = 'Auto-detect from first message';
    sel.appendChild(auto);

    // Build optgroups dynamically from the group field returned by the API
    const grouped = {};
    const groupOrder = [];
    for (const [lang, data] of Object.entries(state.languages)) {
        const g = data.group || 'Other';
        if (!grouped[g]) { grouped[g] = []; groupOrder.push(g); }
        grouped[g].push(lang);
    }
    for (const groupLabel of groupOrder) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = groupLabel;
        for (const lang of grouped[groupLabel]) {
            const opt = document.createElement('option');
            opt.value = lang;
            opt.textContent = lang;
            optgroup.appendChild(opt);
        }
        sel.appendChild(optgroup);
    }
    updateCheckinDialects();
}

function updateCheckinDialects() {
    const lang = document.getElementById('checkin-language').value;
    const sel = document.getElementById('checkin-dialect');
    if (!sel) return;
    sel.innerHTML = '<option value="">— Select —</option>';
    if (lang === AUTO_DETECT_VALUE) {
        sel.disabled = true;
        return;
    }
    sel.disabled = false;
    const dialects = state.languages[lang]?.dialects || [];
    for (const d of dialects) {
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = d;
        sel.appendChild(opt);
    }
}

async function detectLanguageFromText(text) {
    const res = await fetch(`${API}/api/language/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Language detection failed');
    return data;
}

// ---------------------------------------------------------------------------
// Check-In — Setup & Session Start
// ---------------------------------------------------------------------------

async function handleCheckinSetup(e) {
    e.preventDefault();
    const name     = document.getElementById('checkin-name').value.trim();
    const dob      = document.getElementById('checkin-dob').value;
    const language = document.getElementById('checkin-language').value;
    const dialect  = document.getElementById('checkin-dialect').value;
    const cultural = document.getElementById('checkin-cultural').value.trim();

    const autoDetect = language === AUTO_DETECT_VALUE;
    const langData = state.languages[language];
    checkinState.langCode = autoDetect ? 'en' : (langData?.code || 'en');
    checkinState.langName = autoDetect ? 'Auto-detect' : language;
    checkinState.dialect = autoDetect ? '' : (dialect || '');
    checkinState.isAutoMode = true;
    checkinState.pendingLanguageDetect = autoDetect;

    showSpinner('Starting your check-in with Aria…');

    try {
        // Create patient record
        const pRes = await fetch(`${API}/api/patients`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                date_of_birth: dob,
                preferred_language: autoDetect ? 'English' : language,
                dialect: autoDetect ? '' : dialect,
                cultural_context: cultural,
            }),
        });
        const patient = await pRes.json();
        checkinState.patientId = patient.id;

        // Set up chat UI
        document.getElementById('checkin-messages').innerHTML = '';
        document.getElementById('checkin-input').value = '';
        document.getElementById('checkin-chat-title').textContent = name;
        document.getElementById('checkin-lang-badge').textContent =
            autoDetect ? 'Auto-detect' : `${language}${dialect ? ' · ' + dialect : ''}`;
        updateAutoModeUI();

        hideSpinner();
        showCheckinStep('checkin-chat');
        if (autoDetect) {
            const prompt = 'Tell me your symptoms naturally. I will detect your language and continue.';
            appendCheckinBubble('assistant', prompt);
            if (checkinState.isAutoMode) {
                checkinSpeakThenListen(prompt);
            }
        } else {
            // Create pre-consultation session
            const sRes = await fetch(`${API}/api/sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ patient_id: patient.id, session_type: 'pre', language, dialect }),
            });
            const session = await sRes.json();
            checkinState.sessionId = session.session_id;

            if (session.api_key_invalid) {
                document.getElementById('api-key-banner').classList.remove('hidden');
            }

            appendCheckinBubble('assistant', session.greeting);
            if (checkinState.isAutoMode) {
                checkinSpeakThenListen(session.greeting);
            }
        }
    } catch (err) {
        hideSpinner();
        alert('Failed to start check-in. Please check your API key and connection.');
        console.error(err);
    }
}

function backToCheckinSetup() {
    stopCheckinSpeaking();
    stopCheckinVoice();
    checkinState.patientId = null;
    checkinState.sessionId = null;
    checkinState.pendingLanguageDetect = false;
    showCheckinStep('checkin-setup');
}

// ---------------------------------------------------------------------------
// Check-In — Chat Messaging
// ---------------------------------------------------------------------------

async function sendCheckinMessage(textOverride) {
    const input = document.getElementById('checkin-input');
    const text = (textOverride !== undefined ? textOverride : input.value).trim();
    if (!text) return;

    input.value = '';
    input.style.height = 'auto';
    appendCheckinBubble('user', text);
    showCheckinTyping();

    document.getElementById('btn-checkin-send').disabled = true;
    document.getElementById('btn-send-to-doctor').disabled = true;

    try {
        if (!checkinState.sessionId && checkinState.pendingLanguageDetect) {
            const detected = await detectLanguageFromText(text);
            checkinState.langCode = detected.language_code || 'en';
            checkinState.langName = detected.language || 'English';
            checkinState.dialect = detected.dialect || '';
            checkinState.pendingLanguageDetect = false;
            document.getElementById('checkin-lang-badge').textContent =
                `${checkinState.langName}${checkinState.dialect ? ' · ' + checkinState.dialect : ''}`;

            const sRes = await fetch(`${API}/api/sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    patient_id: checkinState.patientId,
                    session_type: 'pre',
                    language: checkinState.langName,
                    dialect: checkinState.dialect,
                }),
            });
            const session = await sRes.json();
            checkinState.sessionId = session.session_id;
            if (session.api_key_invalid) {
                document.getElementById('api-key-banner').classList.remove('hidden');
            }
        }
        if (!checkinState.sessionId) throw new Error('Session not initialized');

        const res = await fetch(`${API}/api/sessions/${checkinState.sessionId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });
        const data = await res.json();
        hideCheckinTyping();

        if (data.api_key_invalid) {
            document.getElementById('api-key-banner').classList.remove('hidden');
        }

        appendCheckinBubble('assistant', data.reply);

        if (checkinState.isAutoMode) {
            checkinSpeakThenListen(data.reply);
        }
    } catch (err) {
        hideCheckinTyping();
        appendCheckinBubble('assistant', '[Connection error — please try again.]');
        console.error(err);
    }

    document.getElementById('btn-checkin-send').disabled = false;
    document.getElementById('btn-send-to-doctor').disabled = false;
}

function handleCheckinKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        stopCheckinVoice();
        sendCheckinMessage();
    }
}

// ---------------------------------------------------------------------------
// Check-In — Complete & Send to Doctor
// ---------------------------------------------------------------------------

async function completeCheckin() {
    if (!checkinState.sessionId) return;
    if (!confirm('End the check-in and send your summary to the doctor?')) return;

    stopCheckinSpeaking();
    stopCheckinVoice();
    showSpinner('Generating clinical summary and sending to Doctor Portal…');

    try {
        const res = await fetch(`${API}/api/sessions/${checkinState.sessionId}/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await res.json();
        hideSpinner();

        document.getElementById('checkin-summary-content').textContent =
            data.patient_summary || data.clinician_summary || 'Summary not available.';

        showCheckinStep('checkin-summary');
    } catch (err) {
        hideSpinner();
        alert('Failed to generate summary. Please try again.');
        console.error(err);
    }
}

// ---------------------------------------------------------------------------
// Check-In — Voice Loop: TTS speak → auto-start STT
// ---------------------------------------------------------------------------

function checkinSpeakThenListen(text) {
    if (!text) return;
    stopCheckinSpeaking();
    stopCheckinVoice();

    setCheckinVoiceIndicator('speaking');
    const bcp47 = resolveSpeechLang(checkinState.langCode, checkinState.dialect);
    checkinState.isSpeaking = true;

    const onDone = () => {
        checkinState.isSpeaking = false;
        checkinUtterance = null;
        checkinAudio = null;
        setCheckinVoiceIndicator('idle');
        if (checkinState.isAutoMode) setTimeout(() => startCheckinListening(), 400);
    };

    playCloudTts(text, bcp47).then(async ({ audio, url }) => {
        checkinAudio = audio;
        audio.onended = () => {
            URL.revokeObjectURL(url);
            onDone();
        };
        audio.onerror = () => {
            URL.revokeObjectURL(url);
            onDone();
        };
        try {
            await audio.play();
        } catch (e) {
            URL.revokeObjectURL(url);
            throw new Error(`Cloud TTS playback failed: ${e.message || e}`);
        }
    }).catch((cloudErr) => {
        console.warn('Cloud TTS unavailable, falling back to browser TTS:', cloudErr);
        if (!('speechSynthesis' in window)) {
            onDone();
            return;
        }

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = bcp47;
        utterance.rate = 0.92;
        utterance.pitch = 1;
        const matched = findVoice(bcp47);
        if (matched) utterance.voice = matched;
        checkinUtterance = utterance;
        utterance.onend = onDone;
        utterance.onerror = onDone;
        speechSynthesis.speak(utterance);
    });
}

function stopCheckinSpeaking() {
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    if (checkinAudio) {
        try { checkinAudio.pause(); } catch (e) { /* ignore */ }
        checkinAudio = null;
    }
    checkinState.isSpeaking = false;
    checkinUtterance = null;
}

// Cache voices — Chrome loads them async, so we store on voiceschanged
let _cachedVoices = [];
if ('speechSynthesis' in window) {
    _cachedVoices = speechSynthesis.getVoices();
    speechSynthesis.onvoiceschanged = () => { _cachedVoices = speechSynthesis.getVoices(); };
}

function findVoice(bcp47) {
    const voices = _cachedVoices.length ? _cachedVoices : speechSynthesis.getVoices();
    const prefix = bcp47.split('-')[0];
    // Exact match first, then same-language prefix (e.g. zh-TW for zh-CN), then language root
    return voices.find(v => v.lang === bcp47) ||
           voices.find(v => v.lang.startsWith(prefix + '-')) ||
           voices.find(v => v.lang === prefix) ||
           null;
}

async function playCloudTts(text, languageCode, pitch = 0, speakingRate = 0.92) {
    const res = await fetch(`${API}/api/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text,
            language_code: languageCode,
            pitch,
            speaking_rate: speakingRate,
        }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `Cloud TTS failed (${res.status})`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    return { audio, url };
}

async function transcribeAudioBlob(audioBlob, languageCode) {
    const form = new FormData();
    const ext = audioBlob.type && audioBlob.type.includes('wav') ? 'wav' : 'webm';
    form.append('audio', audioBlob, `voice.${ext}`);
    if (languageCode) form.append('language', languageCode);

    const res = await fetch(`${API}/api/voice`, {
        method: 'POST',
        body: form,
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data.error || `Voice transcription failed (${res.status})`);
    }

    const text = (data.text || '').trim();
    if (!text) throw new Error('No speech detected');
    return text;
}

// ---------------------------------------------------------------------------
// Check-In — STT (Speech-to-Text)
// Dual-path: MERaLiON (MediaRecorder → /api/voice) or Browser STT fallback
// ---------------------------------------------------------------------------

function startCheckinListening() {
    if (checkinState.isListening) return;
    if (useMeralionStt) {
        _startCheckinMeralion();
    } else {
        _startCheckinBrowserStt();
    }
}

function _startCheckinBrowserStt() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert('Speech recognition is not supported in this browser.');
        return;
    }

    stopCheckinVoice();

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = resolveSpeechLang(checkinState.langCode, checkinState.dialect);

    checkinState.isListening = true;
    checkinRec = rec;
    setCheckinVoiceIndicator('listening');
    document.getElementById('btn-checkin-mic').classList.add('recording');
    document.getElementById('checkin-voice-status').classList.add('active');
    document.getElementById('checkin-status-text').textContent = 'Listening…';

    let finalTranscript = '';

    rec.onresult = (event) => {
        finalTranscript = '';
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const t = event.results[i][0].transcript;
            if (event.results[i].isFinal) finalTranscript += t;
            else interim += t;
        }
        const input = document.getElementById('checkin-input');
        input.value = finalTranscript + interim;
        autoResize(input);
        document.getElementById('checkin-status-text').textContent =
            interim ? 'Hearing you…' : 'Listening…';
    };

    rec.onend = () => {
        checkinState.isListening = false;
        checkinRec = null;
        document.getElementById('btn-checkin-mic').classList.remove('recording');
        document.getElementById('checkin-voice-status').classList.remove('active');
        setCheckinVoiceIndicator('idle');

        if (finalTranscript.trim() && checkinState.isAutoMode) {
            setTimeout(() => sendCheckinMessage(finalTranscript.trim()), 300);
        }
    };

    rec.onerror = (event) => {
        console.warn('Check-in browser STT error:', event.error);
        if (event.error === 'not-allowed') {
            alert('Microphone access was denied. Please allow microphone access to use voice input.');
        }
        checkinState.isListening = false;
        checkinRec = null;
        document.getElementById('btn-checkin-mic').classList.remove('recording');
        document.getElementById('checkin-voice-status').classList.remove('active');
        setCheckinVoiceIndicator('idle');
    };

    try { rec.start(); } catch (e) { console.error('Browser STT start error:', e); }
}

async function _startCheckinMeralion() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
        _startCheckinBrowserStt();
        return;
    }

    stopCheckinVoice();

    try {
        checkinMediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const preferredType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus' : undefined;
        const rec = preferredType
            ? new MediaRecorder(checkinMediaStream, { mimeType: preferredType })
            : new MediaRecorder(checkinMediaStream);

        checkinChunks = [];
        checkinRec = rec;
        checkinState.isListening = true;
        setCheckinVoiceIndicator('listening');
        document.getElementById('btn-checkin-mic').classList.add('recording');
        document.getElementById('checkin-voice-status').classList.add('active');
        document.getElementById('checkin-status-text').textContent = 'Listening (MERaLiON)…';

        rec.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) checkinChunks.push(event.data);
        };

        rec.onstop = async () => {
            const blob = new Blob(checkinChunks, { type: rec.mimeType || 'audio/webm' });
            checkinChunks = [];
            if (checkinMediaStream) {
                checkinMediaStream.getTracks().forEach(t => t.stop());
                checkinMediaStream = null;
            }
            checkinState.isListening = false;
            checkinRec = null;
            document.getElementById('btn-checkin-mic').classList.remove('recording');
            document.getElementById('checkin-voice-status').classList.remove('active');
            setCheckinVoiceIndicator('idle');
            if (!blob.size) return;

            try {
                document.getElementById('checkin-status-text').textContent = 'Transcribing…';
                const transcript = await transcribeAudioBlob(blob, checkinState.langCode);
                document.getElementById('checkin-input').value = transcript;
                autoResize(document.getElementById('checkin-input'));
                document.getElementById('checkin-status-text').textContent = 'Ready';
                if (checkinState.isAutoMode) setTimeout(() => sendCheckinMessage(transcript), 300);
            } catch (e) {
                console.error('MERaLiON STT error, disabling for session:', e);
                useMeralionStt = false;
                document.getElementById('checkin-status-text').textContent = 'MERaLiON unavailable — switched to browser STT';
            }
        };

        rec.start();
        const maxMs = checkinState.isAutoMode ? 6500 : 12000;
        checkinStopTimer = setTimeout(() => stopCheckinVoice(), maxMs);
    } catch (e) {
        console.error('Check-in microphone error:', e);
        alert('Microphone access was denied.');
        checkinState.isListening = false;
        checkinRec = null;
        if (checkinMediaStream) {
            checkinMediaStream.getTracks().forEach(t => t.stop());
            checkinMediaStream = null;
        }
        document.getElementById('btn-checkin-mic').classList.remove('recording');
        document.getElementById('checkin-voice-status').classList.remove('active');
        setCheckinVoiceIndicator('idle');
    }
}

function stopCheckinVoice() {
    checkinState.isListening = false;
    if (checkinStopTimer) {
        clearTimeout(checkinStopTimer);
        checkinStopTimer = null;
    }
    if (checkinRec) {
        try { checkinRec.stop(); } catch (e) { /* ignore */ }
    }
    if (checkinMediaStream) {
        checkinMediaStream.getTracks().forEach(t => t.stop());
        checkinMediaStream = null;
    }
    const micBtn = document.getElementById('btn-checkin-mic');
    const statusBar = document.getElementById('checkin-voice-status');
    if (micBtn) micBtn.classList.remove('recording');
    if (statusBar) statusBar.classList.remove('active');
    setCheckinVoiceIndicator('idle');
}

function toggleCheckinVoice() {
    if (checkinState.isListening) {
        stopCheckinVoice();
    } else {
        stopCheckinSpeaking();
        startCheckinListening();
    }
}

// ---------------------------------------------------------------------------
// Check-In — Auto mode toggle
// ---------------------------------------------------------------------------

function toggleAutoMode() {
    checkinState.isAutoMode = !checkinState.isAutoMode;
    if (!checkinState.isAutoMode) {
        stopCheckinSpeaking();
        stopCheckinVoice();
    }
    updateAutoModeUI();
}

function updateAutoModeUI() {
    const btn = document.getElementById('btn-auto-toggle');
    const label = document.getElementById('auto-mode-label');
    if (!btn || !label) return;
    if (checkinState.isAutoMode) {
        btn.classList.remove('auto-off');
        label.textContent = 'Auto On';
    } else {
        btn.classList.add('auto-off');
        label.textContent = 'Auto Off';
    }
}

// ---------------------------------------------------------------------------
// Check-In — Voice indicator
// ---------------------------------------------------------------------------

function setCheckinVoiceIndicator(indicatorState) {
    const indicator = document.getElementById('checkin-voice-indicator');
    const text = document.getElementById('checkin-voice-status-text');
    if (!indicator || !text) return;
    if (indicatorState === 'idle') {
        indicator.classList.add('hidden');
    } else {
        indicator.classList.remove('hidden');
        text.textContent = indicatorState === 'speaking' ? 'Aria is speaking…' : 'Aria is listening…';
    }
}

// ---------------------------------------------------------------------------
// Check-In — Chat bubble helpers
// ---------------------------------------------------------------------------

function appendCheckinBubble(role, text) {
    const el = document.getElementById('checkin-messages');
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;

    const label = document.createElement('span');
    label.className = 'bubble-label';
    label.textContent = role === 'assistant' ? 'Aria' : 'You';
    bubble.appendChild(label);

    const content = document.createElement('span');
    content.className = 'bubble-text';
    content.textContent = text;
    bubble.appendChild(content);

    el.appendChild(bubble);
    el.scrollTop = el.scrollHeight;
}

function showCheckinTyping() {
    const el = document.getElementById('checkin-messages');
    const ind = document.createElement('div');
    ind.className = 'typing-indicator';
    ind.id = 'checkin-typing';
    ind.innerHTML = '<span></span><span></span><span></span>';
    el.appendChild(ind);
    el.scrollTop = el.scrollHeight;
}

function hideCheckinTyping() {
    const t = document.getElementById('checkin-typing');
    if (t) t.remove();
}

// ---------------------------------------------------------------------------
// Doctor Portal — Session List
// ---------------------------------------------------------------------------

async function loadSessions() {
    const sortBy       = document.getElementById('filter-sort')?.value   || 'newest';
    const statusFilter = document.getElementById('filter-status')?.value || '';
    const urgentOnly   = document.getElementById('filter-urgent')?.value === 'urgent';

    try {
        const res = await fetch(`${API}/api/sessions`);
        let sessions = await res.json();

        // Only show pre-consultation sessions (voice check-ins)
        sessions = sessions.filter(s => s.session_type === 'pre');

        if (statusFilter) sessions = sessions.filter(s => s.status === statusFilter);
        if (urgentOnly)   sessions = sessions.filter(s => s.is_urgent);

        const nameKey = s => (s.patient_name || '').toLowerCase();
        if (sortBy === 'name-az')      sessions = [...sessions].sort((a, b) =>  nameKey(a).localeCompare(nameKey(b)));
        else if (sortBy === 'name-za') sessions = [...sessions].sort((a, b) =>  nameKey(b).localeCompare(nameKey(a)));
        else sessions = [...sessions].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));

        const list = document.getElementById('session-list');
        if (!sessions.length) {
            list.innerHTML = `
                <div class="empty-state">
                    <p>No check-ins found.</p>
                    <p class="text-muted">${urgentOnly ? 'No urgent sessions.' : 'Patient voice check-ins appear here once submitted.'}</p>
                </div>`;
            return;
        }

        list.innerHTML = sessions.map(s => `
            <div class="session-item ${s.is_urgent ? 'session-item-urgent' : ''}" data-id="${s.id}" onclick="loadSessionDetail('${s.id}')">
                <div class="session-item-head">
                    <span class="session-item-name">${escapeHtml(s.patient_name)}</span>
                    ${s.is_urgent ? '<span class="badge badge-urgent">URGENT</span>' : ''}
                </div>
                <div class="session-item-meta">
                    <span class="badge ${s.status === 'completed' ? 'badge-success' : 'badge-warning'}">${s.status}</span>
                    <span>${escapeHtml(s.language_used || '')}${s.dialect_used ? ' · ' + s.dialect_used : ''}</span>
                    <span>${formatDate(s.created_at)}</span>
                </div>
            </div>`).join('');
    } catch (err) {
        console.error('Failed to load sessions', err);
    }
}

async function toggleSessionUrgent(sessionId, isUrgent) {
    try {
        const res = await fetch(`${API}/api/sessions/${sessionId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_urgent: isUrgent }),
        });
        if (!res.ok) throw new Error('Update failed');
        await loadSessionDetail(sessionId);
        loadSessions();
    } catch (err) {
        console.error('Failed to update urgent flag', err);
        alert('Could not update priority. Please try again.');
    }
}

// ---------------------------------------------------------------------------
// Doctor Portal — Session Detail
// ---------------------------------------------------------------------------

async function loadSessionDetail(sessionId) {
    document.querySelectorAll('.session-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === sessionId);
    });

    try {
        const res = await fetch(`${API}/api/sessions/${sessionId}`);
        const s = await res.json();

        const isEnglish = s.language_used === 'English';
        const hasTranslations = s.messages.some(m => m.content_translated);

        const main = document.getElementById('dashboard-main');
        main.innerHTML = `
            <div class="detail-section">
                <div class="detail-section-header">
                    <h3>Patient Information</h3>
                    <button type="button" class="btn ${s.is_urgent ? 'btn-outline' : 'btn-urgent'}" onclick="toggleSessionUrgent('${s.id}', ${!s.is_urgent})">
                        ${s.is_urgent ? 'Unmark urgent' : 'Mark as URGENT'}
                    </button>
                </div>
                ${s.is_urgent ? '<p class="detail-urgent-banner"><strong>URGENT</strong> — Priority handling</p>' : ''}
                <div class="detail-meta">
                    <div class="meta-item"><label>Patient Name</label><span>${escapeHtml(s.patient_name)}</span></div>
                    <div class="meta-item"><label>Date of Birth</label><span>${s.patient_dob || '—'}</span></div>
                    <div class="meta-item"><label>Status</label><span class="badge ${s.status === 'completed' ? 'badge-success' : 'badge-warning'}">${s.status}</span></div>
                    <div class="meta-item"><label>Language</label><span>${s.language_used}${s.dialect_used ? ' (' + s.dialect_used + ')' : ''}</span></div>
                    <div class="meta-item"><label>Check-In Date</label><span>${formatDate(s.created_at)}</span></div>
                </div>
                ${s.patient_cultural_context ? `
                <div style="margin-top:var(--space-2)">
                    <label style="font-size:0.75rem;color:var(--color-muted);font-weight:600;text-transform:uppercase;letter-spacing:0.05em;display:block;margin-bottom:0.25rem;">Cultural Considerations</label>
                    <span style="font-size:0.8125rem">${escapeHtml(s.patient_cultural_context)}</span>
                </div>` : ''}
            </div>

            ${s.clinician_summary ? `
            <div class="detail-section">
                <h3>Clinical Summary (English)</h3>
                <div class="clinician-summary-box">${formatSummaryHtml(s.clinician_summary)}</div>
            </div>` : ''}

            ${s.patient_summary ? `
            <div class="detail-section">
                <h3>Patient Summary (${escapeHtml(s.language_used)})</h3>
                <div class="patient-summary-box">${escapeHtml(s.patient_summary)}</div>
            </div>` : ''}

            <div class="detail-section">
                <h3>Voice Conversation Transcript${!isEnglish && hasTranslations ? ' — Bilingual View' : ''}</h3>
                ${!isEnglish && hasTranslations ? `<p style="font-size:0.8125rem;color:var(--color-muted);margin-bottom:1rem;">Original ${escapeHtml(s.language_used)} text shown alongside English translation.</p>` : ''}
                <div class="transcript-bilingual">
                    ${s.messages.map(m => renderTranscriptMessage(m, s.language_used, isEnglish)).join('')}
                </div>
            </div>`;
    } catch (err) {
        console.error('Failed to load session detail', err);
    }
}

function renderTranscriptMessage(msg, language, isEnglish) {
    const isAssistant = msg.role === 'assistant';
    const speaker = isAssistant ? 'Aria (AI)' : 'Patient';
    const roleClass = isAssistant ? 'role-assistant' : 'role-user';
    const hasTranslation = !isEnglish && msg.content_translated;

    if (isEnglish || !hasTranslation) {
        return `
            <div class="transcript-msg">
                <div class="transcript-msg-header ${roleClass}">${speaker}</div>
                <div class="transcript-msg-body no-translation">
                    <div class="transcript-original">
                        ${isEnglish ? '' : `<span class="transcript-col-label">${escapeHtml(language)}</span>`}
                        <div>${escapeHtml(msg.content)}</div>
                    </div>
                </div>
            </div>`;
    }

    return `
        <div class="transcript-msg">
            <div class="transcript-msg-header ${roleClass}">${speaker}</div>
            <div class="transcript-msg-body">
                <div class="transcript-original">
                    <span class="transcript-col-label">Original (${escapeHtml(language)})</span>
                    <div>${escapeHtml(msg.content)}</div>
                </div>
                <div class="transcript-english">
                    <span class="transcript-col-label">English Translation</span>
                    <div>${escapeHtml(msg.content_translated)}</div>
                </div>
            </div>
        </div>`;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function showSpinner(text) {
    document.getElementById('spinner-text').textContent = text || 'Processing…';
    document.getElementById('spinner-overlay').classList.remove('hidden');
}

function hideSpinner() {
    document.getElementById('spinner-overlay').classList.add('hidden');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(isoStr) {
    if (!isoStr) return '—';
    return new Date(isoStr).toLocaleDateString('en-SG', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}

function formatSummaryHtml(text) {
    if (!text) return '';
    let html = escapeHtml(text);
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/^• /gm, '<span style="color:var(--color-doctor)">&#9679;</span> ');
    return html;
}

// ---------------------------------------------------------------------------
// My Health Agent — State
// ---------------------------------------------------------------------------

let agentState = {
    patientId: null,
    sessionId: null,
    langCode: 'en',
    langName: 'English',
    dialect: '',
    isAutoMode: true,
    isSpeaking: false,
    isListening: false,
    pendingLanguageDetect: false,
    medications: [],
    appointments: [],
    family: [],
};

let agentRec = null;
let agentUtterance = null;
let agentAudio = null;
let _medicationReminderInterval = null;
let agentMediaStream = null;
let agentChunks = [];
let agentStopTimer = null;

// ---------------------------------------------------------------------------
// My Health Agent — Language Dropdowns
// ---------------------------------------------------------------------------

function populateAgentLanguageDropdown() {
    const sel = document.getElementById('agent-language');
    if (!sel) return;
    sel.innerHTML = '';

    const auto = document.createElement('option');
    auto.value = AUTO_DETECT_VALUE;
    auto.textContent = 'Auto-detect from first message';
    sel.appendChild(auto);
    const grouped = {};
    const groupOrder = [];
    for (const [lang, data] of Object.entries(state.languages)) {
        const g = data.group || 'Other';
        if (!grouped[g]) { grouped[g] = []; groupOrder.push(g); }
        grouped[g].push(lang);
    }
    for (const groupLabel of groupOrder) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = groupLabel;
        for (const lang of grouped[groupLabel]) {
            const opt = document.createElement('option');
            opt.value = lang;
            opt.textContent = lang;
            optgroup.appendChild(opt);
        }
        sel.appendChild(optgroup);
    }
    updateAgentDialects();
}

function updateAgentDialects() {
    const lang = document.getElementById('agent-language')?.value;
    const sel = document.getElementById('agent-dialect');
    if (!sel) return;
    sel.innerHTML = '<option value="">— Select —</option>';
    if (lang === AUTO_DETECT_VALUE) {
        sel.disabled = true;
        return;
    }
    sel.disabled = false;
    const dialects = state.languages[lang]?.dialects || [];
    for (const d of dialects) {
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = d;
        sel.appendChild(opt);
    }
}

// ---------------------------------------------------------------------------
// My Health Agent — Setup & Session Start
// ---------------------------------------------------------------------------

async function handleAgentSetup(e) {
    e.preventDefault();
    const name = document.getElementById('agent-name').value.trim();
    const language = document.getElementById('agent-language').value;
    const dialect = document.getElementById('agent-dialect')?.value || '';
    const autoDetect = language === AUTO_DETECT_VALUE;

    const langData = state.languages[language];
    agentState.langCode = autoDetect ? 'en' : (langData?.code || 'en');
    agentState.langName = autoDetect ? 'Auto-detect' : language;
    agentState.dialect = autoDetect ? '' : dialect;
    agentState.isAutoMode = true;
    agentState.pendingLanguageDetect = autoDetect;

    showSpinner('Starting Aria — My Health Assistant…');

    try {
        // Create or reuse patient
        const pRes = await fetch(`${API}/api/patients`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, preferred_language: autoDetect ? 'English' : language }),
        });
        const patient = await pRes.json();
        agentState.patientId = patient.id;

        // Set up UI
        document.getElementById('agent-messages').innerHTML = '';
        document.getElementById('agent-input').value = '';
        document.getElementById('agent-chat-title').textContent = name;
        document.getElementById('agent-lang-badge').textContent = autoDetect ? 'Auto-detect' : language;
        document.getElementById('agent-dash-patient-name').textContent = name;
        updateAgentAutoModeUI();

        hideSpinner();
        showAgentStep('agent-chat');

        requestNotificationPermission();

        if (autoDetect) {
            const prompt = 'Tell me what you need. I will auto-detect your language.';
            appendAgentBubble('assistant', prompt);
            if (agentState.isAutoMode) {
                agentSpeakThenListen(prompt);
            }
        } else {
            // Start agent session
            const sRes = await fetch(`${API}/api/agent/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ patient_id: patient.id, language, patient_name: name }),
            });
            const session = await sRes.json();
            agentState.sessionId = session.session_id;

            appendAgentBubble('assistant', session.greeting);
            if (agentState.isAutoMode) {
                agentSpeakThenListen(session.greeting);
            }
        }

        // Load dashboard data in background
        loadAgentDashboard();
    } catch (err) {
        hideSpinner();
        alert('Failed to start health assistant. Please check your connection.');
        console.error(err);
    }
}

function backToAgentSetup() {
    stopAgentSpeaking();
    stopAgentVoice();
    agentState.patientId = null;
    agentState.sessionId = null;
    agentState.pendingLanguageDetect = false;
    showAgentStep('agent-setup');
}

function showAgentStep(stepId) {
    document.querySelectorAll('.agent-step').forEach(s => s.classList.remove('active'));
    const el = document.getElementById(stepId);
    if (el) el.classList.add('active');
}

// ── HealthHub Live Bridge (WebSocket to port 7001) ────────────────────────────
let _hhWs = null;
let _hhRetry = null;

function _hhConnectWS() {
    if (_hhWs && (_hhWs.readyState === WebSocket.CONNECTING || _hhWs.readyState === WebSocket.OPEN)) return;
    try { _hhWs = new WebSocket('ws://localhost:7001/ws'); } catch (e) { return; }

    _hhWs.onopen = () => {
        const dot = document.getElementById('hh-live-dot');
        if (dot) dot.classList.add('online');
    };
    _hhWs.onclose = () => {
        const dot = document.getElementById('hh-live-dot');
        if (dot) dot.classList.remove('online');
        if (_hhRetry) clearTimeout(_hhRetry);
        _hhRetry = setTimeout(() => {
            if (document.getElementById('view-agent')?.classList.contains('active')) _hhConnectWS();
        }, 3000);
    };
    _hhWs.onerror = () => {};
    _hhWs.onmessage = (ev) => {
        try {
            const msg = JSON.parse(ev.data);
            if (msg.type !== 'screenshot') return;
            const img = document.getElementById('hh-live-img');
            const ph  = document.getElementById('hh-live-placeholder');
            if (img) { img.src = 'data:image/jpeg;base64,' + msg.data; img.style.display = 'block'; }
            if (ph)  ph.style.display = 'none';
            const urlEl = document.getElementById('hh-live-url');
            if (urlEl && msg.url) urlEl.textContent = msg.url.replace('http://localhost:5173', '');
        } catch (e) {}
    };
}

function showAgentDashboard() {
    showAgentStep('agent-dashboard');
    loadAgentDashboard();
}

function backToAgentChat() {
    showAgentStep('agent-chat');
}

// ---------------------------------------------------------------------------
// My Health Agent — Chat Messaging
// ---------------------------------------------------------------------------

async function sendAgentMessage(textOverride) {
    const input = document.getElementById('agent-input');
    const text = (textOverride !== undefined ? textOverride : input.value).trim();
    if (!text) return;

    input.value = '';
    input.style.height = 'auto';
    appendAgentBubble('user', text);
    showAgentTyping();

    document.getElementById('btn-agent-send').disabled = true;

    try {
        if (!agentState.sessionId && agentState.pendingLanguageDetect) {
            const detected = await detectLanguageFromText(text);
            agentState.langCode = detected.language_code || 'en';
            agentState.langName = detected.language || 'English';
            agentState.dialect = detected.dialect || '';
            agentState.pendingLanguageDetect = false;
            document.getElementById('agent-lang-badge').textContent =
                `${agentState.langName}${agentState.dialect ? ' · ' + agentState.dialect : ''}`;

            const sRes = await fetch(`${API}/api/agent/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    patient_id: agentState.patientId,
                    language: agentState.langName,
                    patient_name: document.getElementById('agent-chat-title')?.textContent || '',
                }),
            });
            const session = await sRes.json();
            agentState.sessionId = session.session_id;
        }
        if (!agentState.sessionId) throw new Error('Agent session not initialized');

        const res = await fetch(`${API}/api/agent/sessions/${agentState.sessionId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });
        const data = await res.json();
        hideAgentTyping();

        appendAgentBubble('assistant', data.reply);

        if (agentState.isAutoMode) {
            agentSpeakThenListen(data.reply);
        }

        // Refresh dashboard data after each message (tools may have run)
        setTimeout(loadAgentDashboard, 800);
    } catch (err) {
        hideAgentTyping();
        appendAgentBubble('assistant', '[Connection error — please try again.]');
        console.error(err);
    }

    document.getElementById('btn-agent-send').disabled = false;
}

function handleAgentKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        stopAgentVoice();
        sendAgentMessage();
    }
}

// ---------------------------------------------------------------------------
// My Health Agent — Voice Loop (TTS → STT)
// ---------------------------------------------------------------------------

function agentSpeakThenListen(text) {
    if (!text) return;
    stopAgentSpeaking();
    stopAgentVoice();

    setAgentVoiceIndicator('speaking');
    const bcp47 = resolveSpeechLang(agentState.langCode, agentState.dialect);
    agentState.isSpeaking = true;

    const onDone = () => {
        agentState.isSpeaking = false;
        agentUtterance = null;
        agentAudio = null;
        setAgentVoiceIndicator('idle');
        if (agentState.isAutoMode) setTimeout(() => startAgentListening(), 400);
    };

    playCloudTts(text, bcp47).then(async ({ audio, url }) => {
        agentAudio = audio;
        audio.onended = () => {
            URL.revokeObjectURL(url);
            onDone();
        };
        audio.onerror = () => {
            URL.revokeObjectURL(url);
            onDone();
        };
        try {
            await audio.play();
        } catch (e) {
            URL.revokeObjectURL(url);
            throw new Error(`Cloud TTS playback failed: ${e.message || e}`);
        }
    }).catch((cloudErr) => {
        console.warn('Cloud TTS unavailable, falling back to browser TTS:', cloudErr);
        if (!('speechSynthesis' in window)) {
            onDone();
            return;
        }
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = bcp47;
        utterance.rate = 0.92;
        utterance.pitch = 1;
        const matched = findVoice(bcp47);
        if (matched) utterance.voice = matched;
        agentUtterance = utterance;
        utterance.onend = onDone;
        utterance.onerror = onDone;
        speechSynthesis.speak(utterance);
    });
}

function stopAgentSpeaking() {
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    if (agentAudio) {
        try { agentAudio.pause(); } catch (e) { /* ignore */ }
        agentAudio = null;
    }
    agentState.isSpeaking = false;
    agentUtterance = null;
}

function startAgentListening() {
    if (agentState.isListening) return;
    if (useMeralionStt) {
        _startAgentMeralion();
    } else {
        _startAgentBrowserStt();
    }
}

function _startAgentBrowserStt() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert('Speech recognition is not supported in this browser.');
        return;
    }

    stopAgentVoice();

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = resolveSpeechLang(agentState.langCode, agentState.dialect);

    agentState.isListening = true;
    agentRec = rec;
    setAgentVoiceIndicator('listening');
    document.getElementById('btn-agent-mic').classList.add('recording');
    document.getElementById('agent-voice-status').classList.add('active');
    document.getElementById('agent-status-text').textContent = 'Listening…';

    let finalTranscript = '';

    rec.onresult = (event) => {
        finalTranscript = '';
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const t = event.results[i][0].transcript;
            if (event.results[i].isFinal) finalTranscript += t;
            else interim += t;
        }
        const input = document.getElementById('agent-input');
        input.value = finalTranscript + interim;
        autoResize(input);
        document.getElementById('agent-status-text').textContent =
            interim ? 'Hearing you…' : 'Listening…';
    };

    rec.onend = () => {
        agentState.isListening = false;
        agentRec = null;
        document.getElementById('btn-agent-mic').classList.remove('recording');
        document.getElementById('agent-voice-status').classList.remove('active');
        setAgentVoiceIndicator('idle');

        if (finalTranscript.trim() && agentState.isAutoMode) {
            setTimeout(() => sendAgentMessage(finalTranscript.trim()), 300);
        }
    };

    rec.onerror = (event) => {
        console.warn('Agent browser STT error:', event.error);
        if (event.error === 'not-allowed') {
            alert('Microphone access was denied. Please allow microphone access to use voice input.');
        }
        agentState.isListening = false;
        agentRec = null;
        document.getElementById('btn-agent-mic').classList.remove('recording');
        document.getElementById('agent-voice-status').classList.remove('active');
        setAgentVoiceIndicator('idle');
    };

    try { rec.start(); } catch (e) { console.error('Agent browser STT start error:', e); }
}

async function _startAgentMeralion() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
        _startAgentBrowserStt();
        return;
    }

    stopAgentVoice();

    try {
        agentMediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const preferredType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus' : undefined;
        const rec = preferredType
            ? new MediaRecorder(agentMediaStream, { mimeType: preferredType })
            : new MediaRecorder(agentMediaStream);

        agentChunks = [];
        agentRec = rec;
        agentState.isListening = true;
        setAgentVoiceIndicator('listening');
        document.getElementById('btn-agent-mic').classList.add('recording');
        document.getElementById('agent-voice-status').classList.add('active');
        document.getElementById('agent-status-text').textContent = 'Listening (MERaLiON)…';

        rec.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) agentChunks.push(event.data);
        };

        rec.onstop = async () => {
            const blob = new Blob(agentChunks, { type: rec.mimeType || 'audio/webm' });
            agentChunks = [];
            if (agentMediaStream) {
                agentMediaStream.getTracks().forEach(t => t.stop());
                agentMediaStream = null;
            }
            agentState.isListening = false;
            agentRec = null;
            document.getElementById('btn-agent-mic').classList.remove('recording');
            document.getElementById('agent-voice-status').classList.remove('active');
            setAgentVoiceIndicator('idle');
            if (!blob.size) return;

            try {
                document.getElementById('agent-status-text').textContent = 'Transcribing…';
                const transcript = await transcribeAudioBlob(blob, agentState.langCode);
                document.getElementById('agent-input').value = transcript;
                autoResize(document.getElementById('agent-input'));
                document.getElementById('agent-status-text').textContent = 'Ready';
                if (agentState.isAutoMode) setTimeout(() => sendAgentMessage(transcript), 300);
            } catch (e) {
                console.error('Agent MERaLiON STT error, disabling for session:', e);
                useMeralionStt = false;
                document.getElementById('agent-status-text').textContent = 'MERaLiON unavailable — switched to browser STT';
            }
        };

        rec.start();
        const maxMs = agentState.isAutoMode ? 6500 : 12000;
        agentStopTimer = setTimeout(() => stopAgentVoice(), maxMs);
    } catch (e) {
        console.error('Agent microphone error:', e);
        alert('Microphone access was denied.');
        agentState.isListening = false;
        agentRec = null;
        if (agentMediaStream) {
            agentMediaStream.getTracks().forEach(t => t.stop());
            agentMediaStream = null;
        }
        document.getElementById('btn-agent-mic').classList.remove('recording');
        document.getElementById('agent-voice-status').classList.remove('active');
        setAgentVoiceIndicator('idle');
    }
}

function stopAgentVoice() {
    agentState.isListening = false;
    if (agentStopTimer) {
        clearTimeout(agentStopTimer);
        agentStopTimer = null;
    }
    if (agentRec) {
        try { agentRec.stop(); } catch (e) { /* ignore */ }
    }
    if (agentMediaStream) {
        agentMediaStream.getTracks().forEach(t => t.stop());
        agentMediaStream = null;
    }
    const micBtn = document.getElementById('btn-agent-mic');
    const statusBar = document.getElementById('agent-voice-status');
    if (micBtn) micBtn.classList.remove('recording');
    if (statusBar) statusBar.classList.remove('active');
    setAgentVoiceIndicator('idle');
}

function toggleAgentVoice() {
    if (agentState.isListening) {
        stopAgentVoice();
    } else {
        stopAgentSpeaking();
        startAgentListening();
    }
}

function toggleAgentAutoMode() {
    agentState.isAutoMode = !agentState.isAutoMode;
    if (!agentState.isAutoMode) {
        stopAgentSpeaking();
        stopAgentVoice();
    }
    updateAgentAutoModeUI();
}

function updateAgentAutoModeUI() {
    const btn = document.getElementById('btn-agent-auto-toggle');
    const label = document.getElementById('agent-auto-mode-label');
    if (!btn || !label) return;
    if (agentState.isAutoMode) {
        btn.classList.remove('auto-off');
        label.textContent = 'Auto On';
    } else {
        btn.classList.add('auto-off');
        label.textContent = 'Auto Off';
    }
}

function setAgentVoiceIndicator(indicatorState) {
    const indicator = document.getElementById('agent-voice-indicator');
    const text = document.getElementById('agent-voice-status-text');
    if (!indicator || !text) return;
    if (indicatorState === 'idle') {
        indicator.classList.add('hidden');
    } else {
        indicator.classList.remove('hidden');
        text.textContent = indicatorState === 'speaking' ? 'Aria is speaking…' : 'Aria is listening…';
    }
}

// ---------------------------------------------------------------------------
// My Health Agent — Chat Bubble Helpers
// ---------------------------------------------------------------------------

function appendAgentBubble(role, text) {
    const el = document.getElementById('agent-messages');
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;

    const label = document.createElement('span');
    label.className = 'bubble-label';
    label.textContent = role === 'assistant' ? 'Aria' : 'You';
    bubble.appendChild(label);

    const content = document.createElement('span');
    content.className = 'bubble-text';
    content.textContent = text;
    bubble.appendChild(content);

    el.appendChild(bubble);
    el.scrollTop = el.scrollHeight;
}

function showAgentTyping() {
    const el = document.getElementById('agent-messages');
    const ind = document.createElement('div');
    ind.className = 'typing-indicator';
    ind.id = 'agent-typing';
    ind.innerHTML = '<span></span><span></span><span></span>';
    el.appendChild(ind);
    el.scrollTop = el.scrollHeight;
}

function hideAgentTyping() {
    const t = document.getElementById('agent-typing');
    if (t) t.remove();
}

// ---------------------------------------------------------------------------
// My Health Agent — Dashboard
// ---------------------------------------------------------------------------

async function loadAgentDashboard() {
    if (!agentState.patientId) return;

    try {
        const res = await fetch(`${API}/api/health-summary?patient_id=${agentState.patientId}`);
        const data = await res.json();

        agentState.appointments = data.upcoming_appointments || [];
        agentState.medications = data.active_medications || [];
        agentState.family = data.family_members || [];

        renderDashboardFull(data);
        renderDashboardStrip(data);
        scheduleMedicationReminders(agentState.medications);
    } catch (err) {
        console.error('Failed to load health summary', err);
    }
}

function renderDashboardFull(data) {
    const apptEl = document.getElementById('dash-appointments');
    const medEl = document.getElementById('dash-medications');
    const famEl = document.getElementById('dash-family');
    if (!apptEl) return;

    renderAppointmentCards(data.upcoming_appointments || [], apptEl);
    renderMedicationCards(data.active_medications || [], medEl);
    renderFamilyCards(data.family_members || [], famEl);
}

function renderDashboardStrip(data) {
    const stripEl = document.getElementById('strip-cards');
    if (!stripEl) return;

    const appts = data.upcoming_appointments || [];
    const meds = data.active_medications || [];

    let html = '';

    if (appts.length > 0) {
        const a = appts[0];
        html += `<div class="health-card appointment">
            <div class="health-card-icon">📅</div>
            <div class="health-card-body">
                <div class="health-card-title">${escapeHtml(a.doctor)}</div>
                <div class="health-card-sub">${escapeHtml(a.datetime)}</div>
            </div>
        </div>`;
    }

    if (meds.length > 0) {
        const m = meds[0];
        const nextReminder = m.reminder_times && m.reminder_times.length ? m.reminder_times[0] : '';
        html += `<div class="health-card medication">
            <div class="health-card-icon">💊</div>
            <div class="health-card-body">
                <div class="health-card-title">${escapeHtml(m.name)} ${escapeHtml(m.dosage)}</div>
                <div class="health-card-sub">${nextReminder ? 'Next: ' + nextReminder : escapeHtml(m.frequency)}</div>
            </div>
        </div>`;
    }

    if (appts.length > 1 || meds.length > 1) {
        html += `<div class="health-card summary-card" onclick="showAgentDashboard()" style="cursor:pointer;">
            <div class="health-card-icon">➕</div>
            <div class="health-card-body">
                <div class="health-card-title">${appts.length} appointments</div>
                <div class="health-card-sub">${meds.length} medications</div>
            </div>
        </div>`;
    }

    stripEl.innerHTML = html;

    if (html) {
        document.getElementById('agent-dashboard-strip').classList.remove('hidden');
    }
}

function toggleDashboardStrip() {
    const strip = document.getElementById('agent-dashboard-strip');
    if (strip) strip.classList.toggle('hidden');
}

function renderAppointmentCards(appointments, container) {
    if (!container) return;
    if (!appointments.length) {
        container.innerHTML = '<p class="text-muted" style="font-size:0.85rem;">No upcoming appointments.</p>';
        return;
    }
    container.innerHTML = appointments.map(a => `
        <div class="health-card appointment">
            <div class="health-card-icon">📅</div>
            <div class="health-card-body">
                <div class="health-card-title">${escapeHtml(a.doctor)}</div>
                <div class="health-card-sub">${escapeHtml(a.specialty)} · ${escapeHtml(a.datetime)}</div>
                ${a.reason ? `<div class="health-card-note">${escapeHtml(a.reason)}</div>` : ''}
                ${a.for && a.for !== 'self' ? `<div class="health-card-for">For: ${escapeHtml(a.for)}</div>` : ''}
            </div>
        </div>`).join('');
}

function renderMedicationCards(medications, container) {
    if (!container) return;
    if (!medications.length) {
        container.innerHTML = '<p class="text-muted" style="font-size:0.85rem;">No active medications.</p>';
        return;
    }
    container.innerHTML = medications.map(m => {
        const reminders = m.reminder_times || [];
        return `<div class="health-card medication">
            <div class="health-card-icon">💊</div>
            <div class="health-card-body">
                <div class="health-card-title">${escapeHtml(m.name)} ${escapeHtml(m.dosage)}</div>
                <div class="health-card-sub">${escapeHtml(m.frequency)}</div>
                ${reminders.length ? `<div class="health-card-note">Reminders: ${reminders.join(', ')}</div>` : ''}
                ${m.for && m.for !== 'self' ? `<div class="health-card-for">For: ${escapeHtml(m.for)}</div>` : ''}
            </div>
        </div>`;
    }).join('');
}

function renderFamilyCards(members, container) {
    if (!container) return;
    if (!members.length) {
        container.innerHTML = '<p class="text-muted" style="font-size:0.85rem;">No family members registered.</p>';
        return;
    }
    container.innerHTML = members.map(f => `
        <div class="health-card family">
            <div class="health-card-icon">👤</div>
            <div class="health-card-body">
                <div class="health-card-title">${escapeHtml(f.name)}</div>
                <div class="health-card-sub">${escapeHtml(f.relationship)}</div>
                ${f.date_of_birth ? `<div class="health-card-note">DOB: ${escapeHtml(f.date_of_birth)}</div>` : ''}
            </div>
        </div>`).join('');
}

// ---------------------------------------------------------------------------
// My Health Agent — Medication Reminders (Browser Notifications)
// ---------------------------------------------------------------------------

function requestNotificationPermission() {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
        const banner = document.getElementById('notification-permission-banner');
        if (banner) banner.classList.remove('hidden');
    } else if (Notification.permission === 'granted') {
        startMedicationReminderLoop();
    }
}

async function enableNotifications() {
    if (!('Notification' in window)) return;
    const permission = await Notification.requestPermission();
    const banner = document.getElementById('notification-permission-banner');
    if (banner) banner.classList.add('hidden');
    if (permission === 'granted') {
        startMedicationReminderLoop();
    }
}

function startMedicationReminderLoop() {
    if (_medicationReminderInterval) return;
    _medicationReminderInterval = setInterval(checkMedicationReminders, 60000);
}

function scheduleMedicationReminders(meds) {
    agentState.medications = meds;
    if (Notification.permission === 'granted') {
        startMedicationReminderLoop();
    }
}

function checkMedicationReminders() {
    if (Notification.permission !== 'granted') return;
    if (!agentState.medications.length) return;

    const now = new Date();
    const hhmm = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
    const todayKey = now.toDateString();

    const notified = JSON.parse(sessionStorage.getItem('medNotifiedToday') || '{}');

    for (const med of agentState.medications) {
        const reminders = med.reminder_times || [];
        for (const time of reminders) {
            const notifyKey = `${med.id}_${time}_${todayKey}`;
            if (time === hhmm && !notified[notifyKey]) {
                notified[notifyKey] = true;
                sessionStorage.setItem('medNotifiedToday', JSON.stringify(notified));
                new Notification('Medication Reminder', {
                    body: `Time to take your ${med.name} ${med.dosage}`,
                    icon: '/favicon.ico',
                });
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', init);
