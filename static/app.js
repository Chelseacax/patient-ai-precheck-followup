/* ==========================================================================
   MedBridge — Frontend Application Logic
   Dual-portal: Patient Portal + Doctor Portal
   Voice: Speech-to-Text (mic input) + Text-to-Speech (read aloud)
   ========================================================================== */

const API = '';  // Same origin

// ---------------------------------------------------------------------------
// Speech language mapping (our code → BCP 47 for Web Speech API)
// ---------------------------------------------------------------------------

const SPEECH_LANG_MAP = {
    'en':            'en-SG',
    'zh':            'zh-CN',
    'ms':            'ms-MY',
    'ta':            'ta-SG',
    'zh-hokkien':    'zh-CN',    // closest supported
    'zh-teochew':    'zh-CN',    // closest supported
    'zh-cantonese':  'zh-HK',
    'zh-hakka':      'zh-CN',    // closest supported
    'zh-hainanese':  'zh-CN',    // closest supported
    'hi':            'hi-IN',
    'tl':            'fil-PH',
    'vi':            'vi-VN',
    'th':            'th-TH',
    'id':            'id-ID',
    'my':            'my-MM',
    'bn':            'bn-BD',
    'km':            'km-KH',
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let state = {
    languages: {},
    currentPatientId: null,
    currentSessionId: null,
    currentView: 'home',
    currentLangCode: 'en',       // language code for speech APIs
    currentLangName: 'English',  // display name
};

// Voice state
let recognition = null;    // SpeechRecognition instance
let isRecording = false;
let currentUtterance = null;  // current SpeechSynthesis utterance

// Accessibility (patient portal) — visual tools
const A11Y_STORAGE_KEY = 'medbridge_a11y';
let a11yState = {
    magnifier: 'off',
    theme: 'default',
    textSize: 'normal',
    reducedMotion: false,
    focusVisible: false,
};
let a11yLoupeRAF = null;
let a11yLoupeThrottle = null;

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
    if (view === 'patient') showPatientStep('patient-register');

    updateA11yToolbarVisibility();
    if (view !== 'patient') setA11yLoupe(false);

    // Stop any ongoing speech when switching views
    stopSpeaking();
    stopRecording();
}

function showPatientStep(stepId) {
    document.querySelectorAll('.patient-step').forEach(s => s.classList.remove('active'));
    document.getElementById(stepId).classList.add('active');
}

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

async function init() {
    try {
        const res = await fetch(`${API}/api/languages`);
        state.languages = await res.json();
        populateLanguageDropdown();
    } catch (e) {
        console.error('Failed to load languages', e);
    }
    checkApiKey();
    loadA11ySettings();
    syncA11yPanelFromState();
    applyA11ySettings();
    initA11yPanelListeners();
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
            alert('API key saved successfully! You can now start sessions.');
        } else {
            alert(`Failed to save: ${data.error}`);
        }
    } catch (e) {
        alert('Network error while saving API key.');
        console.error(e);
    }
    input.disabled = false;
}

function dismissBanner() {
    document.getElementById('api-key-banner').classList.add('hidden');
}

// ---------------------------------------------------------------------------
// Patient Portal — Visual Accessibility
// ---------------------------------------------------------------------------

function loadA11ySettings() {
    try {
        const raw = localStorage.getItem(A11Y_STORAGE_KEY);
        if (raw) {
            const saved = JSON.parse(raw);
            a11yState = { ...a11yState, ...saved };
        }
    } catch (e) {
        console.warn('Could not load a11y settings', e);
    }
}

function saveA11ySettings() {
    try {
        localStorage.setItem(A11Y_STORAGE_KEY, JSON.stringify(a11yState));
    } catch (e) {
        console.warn('Could not save a11y settings', e);
    }
}

function applyA11ySettings() {
    const body = document.body;
    const html = document.documentElement;

    // Magnifier: page zoom classes
    body.classList.remove('a11y-zoom-125', 'a11y-zoom-150', 'a11y-zoom-200');
    html.classList.remove('a11y-page-zoom');
    if (a11yState.magnifier === '125') {
        body.classList.add('a11y-zoom-125');
        html.classList.add('a11y-page-zoom');
    } else if (a11yState.magnifier === '150') {
        body.classList.add('a11y-zoom-150');
        html.classList.add('a11y-page-zoom');
    } else if (a11yState.magnifier === '200') {
        body.classList.add('a11y-zoom-200');
        html.classList.add('a11y-page-zoom');
    }

    setA11yLoupe(a11yState.magnifier === 'loupe');

    // Theme
    body.classList.remove('a11y-theme-high-contrast-light', 'a11y-theme-high-contrast-dark');
    if (a11yState.theme === 'high-contrast-light') body.classList.add('a11y-theme-high-contrast-light');
    else if (a11yState.theme === 'high-contrast-dark') body.classList.add('a11y-theme-high-contrast-dark');

    // Text size
    html.classList.toggle('a11y-text-large', a11yState.textSize === 'large');

    // Reduced motion
    body.classList.toggle('a11y-reduced-motion', a11yState.reducedMotion);

    // Strong focus
    body.classList.toggle('a11y-focus-visible', a11yState.focusVisible);
}

function updateA11yToolbarVisibility() {
    const wrap = document.getElementById('a11y-toolbar-wrap');
    if (!wrap) return;
    if (state.currentView === 'patient') {
        wrap.classList.remove('hidden');
    } else {
        wrap.classList.add('hidden');
        document.getElementById('a11y-panel').classList.add('hidden');
    }
}

function toggleA11yPanel() {
    const panel = document.getElementById('a11y-panel');
    panel.classList.toggle('hidden');
}

function initA11yPanelListeners() {
    const panel = document.getElementById('a11y-panel');
    if (!panel) return;

    const magnifierRadios = panel.querySelectorAll('input[name="a11y-magnifier"]');
    magnifierRadios.forEach(r => {
        r.addEventListener('change', () => {
            a11yState.magnifier = r.value;
            applyA11ySettings();
            saveA11ySettings();
        });
    });

    const themeRadios = panel.querySelectorAll('input[name="a11y-theme"]');
    themeRadios.forEach(r => {
        r.addEventListener('change', () => {
            a11yState.theme = r.value;
            applyA11ySettings();
            saveA11ySettings();
        });
    });

    const textRadios = panel.querySelectorAll('input[name="a11y-text"]');
    textRadios.forEach(r => {
        r.addEventListener('change', () => {
            a11yState.textSize = r.value;
            applyA11ySettings();
            saveA11ySettings();
        });
    });

    const reducedMotion = panel.querySelector('input[name="a11y-reduced-motion"]');
    if (reducedMotion) {
        reducedMotion.addEventListener('change', () => {
            a11yState.reducedMotion = reducedMotion.checked;
            applyA11ySettings();
            saveA11ySettings();
        });
    }

    const focusVisible = panel.querySelector('input[name="a11y-focus-visible"]');
    if (focusVisible) {
        focusVisible.addEventListener('change', () => {
            a11yState.focusVisible = focusVisible.checked;
            applyA11ySettings();
            saveA11ySettings();
        });
    }
}

function syncA11yPanelFromState() {
    const panel = document.getElementById('a11y-panel');
    if (!panel) return;
    const mag = panel.querySelector(`input[name="a11y-magnifier"][value="${a11yState.magnifier}"]`);
    if (mag) mag.checked = true;
    const th = panel.querySelector(`input[name="a11y-theme"][value="${a11yState.theme}"]`);
    if (th) th.checked = true;
    const tx = panel.querySelector(`input[name="a11y-text"][value="${a11yState.textSize}"]`);
    if (tx) tx.checked = true;
    const rm = panel.querySelector('input[name="a11y-reduced-motion"]');
    if (rm) rm.checked = a11yState.reducedMotion;
    const fv = panel.querySelector('input[name="a11y-focus-visible"]');
    if (fv) fv.checked = a11yState.focusVisible;
}

function setA11yLoupe(on) {
    const loupe = document.getElementById('a11y-loupe');
    if (!loupe) return;
    if (on) {
        loupe.classList.remove('hidden');
        loupe.innerHTML = '';
        document.addEventListener('mousemove', a11yLoupeMove, { passive: true });
    } else {
        loupe.classList.add('hidden');
        loupe.innerHTML = '';
        document.removeEventListener('mousemove', a11yLoupeMove);
        if (a11yLoupeRAF) cancelAnimationFrame(a11yLoupeRAF);
    }
}

function a11yLoupeMove(e) {
    if (a11yLoupeThrottle) return;
    a11yLoupeThrottle = requestAnimationFrame(() => {
        a11yLoupeThrottle = null;
        const loupe = document.getElementById('a11y-loupe');
        if (!loupe || loupe.classList.contains('hidden')) return;
        const x = e.clientX;
        const y = e.clientY;
        const size = 180;
        loupe.style.left = (x - size / 2) + 'px';
        loupe.style.top = (y - size / 2) + 'px';

        loupe.style.pointerEvents = 'none';
        const el = document.elementFromPoint(x, y);
        if (!el || el === document.body || el === document.documentElement || el.closest('#a11y-toolbar-wrap')) return;
        const rect = el.getBoundingClientRect();
        try {
            const clone = el.cloneNode(true);
            const cx = x - rect.left;
            const cy = y - rect.top;
            clone.style.cssText = `position:fixed;left:${(size/2) - cx * 2}px;top:${(size/2) - cy * 2}px;transform:scale(2);transform-origin:0 0;pointer-events:none;background:var(--color-surface,#fff);color:var(--color-text,#111);max-width:400px;overflow:hidden;border-radius:4px;`;
            clone.setAttribute('aria-hidden', 'true');
            loupe.innerHTML = '';
            loupe.appendChild(clone);
        } catch (err) {
            loupe.innerHTML = '';
        }
    });
}

function populateLanguageDropdown() {
    const sel = document.getElementById('reg-language');
    sel.innerHTML = '';

    const langs = Object.keys(state.languages);
    // Group: Official (first 4), Dialects (next 5), SEA (rest)
    const groups = [
        { label: 'Singapore Official Languages', items: langs.slice(0, 4) },
        { label: 'Singapore Chinese Dialects', items: langs.slice(4, 9) },
        { label: 'Southeast Asian Languages', items: langs.slice(9) },
    ];

    for (const group of groups) {
        if (group.items.length === 0) continue;
        const optgroup = document.createElement('optgroup');
        optgroup.label = group.label;
        for (const lang of group.items) {
            const opt = document.createElement('option');
            opt.value = lang;
            opt.textContent = lang;
            optgroup.appendChild(opt);
        }
        sel.appendChild(optgroup);
    }
    updateDialects();
}

function updateDialects() {
    const lang = document.getElementById('reg-language').value;
    const sel = document.getElementById('reg-dialect');
    sel.innerHTML = '<option value="">— Select —</option>';
    const dialects = state.languages[lang]?.dialects || [];
    for (const d of dialects) {
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = d;
        sel.appendChild(opt);
    }
}

// ---------------------------------------------------------------------------
// Patient Registration & Session Start
// ---------------------------------------------------------------------------

async function handleRegister(e) {
    e.preventDefault();
    const name = document.getElementById('reg-name').value.trim();
    const dob = document.getElementById('reg-dob').value;
    const language = document.getElementById('reg-language').value;
    const dialect = document.getElementById('reg-dialect').value;
    const cultural = document.getElementById('reg-cultural').value.trim();
    const sessionType = document.querySelector('input[name="session-type"]:checked').value;

    // Store language info for speech APIs
    const langData = state.languages[language];
    state.currentLangCode = langData?.code || 'en';
    state.currentLangName = language;

    showSpinner('Setting up your session…');

    try {
        // Create patient
        const pRes = await fetch(`${API}/api/patients`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                date_of_birth: dob,
                preferred_language: language,
                dialect,
                cultural_context: cultural,
            }),
        });
        const patient = await pRes.json();
        state.currentPatientId = patient.id;

        // Create session
        const sRes = await fetch(`${API}/api/sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                patient_id: patient.id,
                session_type: sessionType,
                language,
                dialect,
            }),
        });
        const session = await sRes.json();
        state.currentSessionId = session.session_id;

        // If API key is invalid, show the banner
        if (session.api_key_invalid) {
            const banner = document.getElementById('api-key-banner');
            banner.classList.remove('hidden');
            banner.querySelector('span').innerHTML =
                '<strong>Your API key is invalid or expired.</strong> Please enter a valid OpenAI (sk-...) or Groq (gsk_...) API key.';
        }

        // Set up chat UI
        document.getElementById('chat-title').textContent = name;
        document.getElementById('chat-lang-badge').textContent = `${language}${dialect ? ' · ' + dialect : ''}`;
        document.getElementById('chat-type-badge').textContent = sessionType === 'pre' ? 'Pre-Consultation' : 'Post-Consultation';
        document.getElementById('chat-type-badge').className = `badge ${sessionType === 'pre' ? 'badge-pre' : 'badge-post'}`;

        const messagesEl = document.getElementById('chat-messages');
        messagesEl.innerHTML = '';
        appendBubble('assistant', session.greeting);

        hideSpinner();
        showPatientStep('patient-chat');
        document.getElementById('chat-input').focus();
    } catch (err) {
        hideSpinner();
        alert('Failed to start session. Please check your connection and API key.');
        console.error(err);
    }
}

// ---------------------------------------------------------------------------
// Chat (Patient Portal)
// ---------------------------------------------------------------------------

function appendBubble(role, text) {
    const el = document.getElementById('chat-messages');
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;

    const label = document.createElement('span');
    label.className = 'bubble-label';
    label.textContent = role === 'assistant' ? 'MedBridge' : 'You';
    bubble.appendChild(label);

    const content = document.createElement('span');
    content.className = 'bubble-text';
    content.textContent = text;
    bubble.appendChild(content);

    // Add speaker button for assistant messages
    if (role === 'assistant') {
        const actions = document.createElement('div');
        actions.className = 'bubble-actions';

        const speakBtn = document.createElement('button');
        speakBtn.className = 'btn-speak';
        speakBtn.setAttribute('data-text', text);
        speakBtn.onclick = function() { toggleSpeak(this, text); };
        speakBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
            <span class="speak-label">Listen</span>`;
        actions.appendChild(speakBtn);
        bubble.appendChild(actions);
    }

    el.appendChild(bubble);
    el.scrollTop = el.scrollHeight;
}

function showTyping() {
    const el = document.getElementById('chat-messages');
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.id = 'typing';
    indicator.innerHTML = '<span></span><span></span><span></span>';
    el.appendChild(indicator);
    el.scrollTop = el.scrollHeight;
}

function hideTyping() {
    const t = document.getElementById('typing');
    if (t) t.remove();
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text || !state.currentSessionId) return;

    input.value = '';
    input.style.height = 'auto';
    appendBubble('user', text);
    showTyping();

    document.getElementById('btn-send').disabled = true;
    document.getElementById('btn-complete').disabled = true;

    try {
        const res = await fetch(`${API}/api/sessions/${state.currentSessionId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });
        const data = await res.json();
        hideTyping();

        if (data.api_key_invalid) {
            const banner = document.getElementById('api-key-banner');
            banner.classList.remove('hidden');
            banner.querySelector('span').innerHTML =
                '<strong>Your API key is invalid or expired.</strong> Please enter a valid OpenAI (sk-...) or Groq (gsk_...) API key.';
        }

        appendBubble('assistant', data.reply);
    } catch (err) {
        hideTyping();
        appendBubble('assistant', '[Connection error — please try again.]');
        console.error(err);
    }

    document.getElementById('btn-send').disabled = false;
    document.getElementById('btn-complete').disabled = false;
    input.focus();
}

function handleChatKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// ---------------------------------------------------------------------------
// Text-to-Speech (TTS) — Read AI messages aloud
// ---------------------------------------------------------------------------

function getSpeechLang() {
    return SPEECH_LANG_MAP[state.currentLangCode] || 'en-SG';
}

function toggleSpeak(btn, text) {
    if (!('speechSynthesis' in window)) {
        alert('Text-to-speech is not supported in your browser. Please use Chrome or Safari.');
        return;
    }

    // If currently speaking this text, stop it
    if (btn.classList.contains('speaking')) {
        stopSpeaking();
        return;
    }

    // Stop any other utterance first
    stopSpeaking();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = getSpeechLang();
    utterance.rate = 0.9;
    utterance.pitch = 1;

    // Try to find a matching voice
    const voices = speechSynthesis.getVoices();
    const targetLang = getSpeechLang();
    const matchedVoice = voices.find(v => v.lang === targetLang) ||
                         voices.find(v => v.lang.startsWith(targetLang.split('-')[0]));
    if (matchedVoice) {
        utterance.voice = matchedVoice;
    }

    btn.classList.add('speaking');
    btn.querySelector('.speak-label').textContent = 'Stop';
    currentUtterance = utterance;

    utterance.onend = () => {
        btn.classList.remove('speaking');
        btn.querySelector('.speak-label').textContent = 'Listen';
        currentUtterance = null;
    };
    utterance.onerror = () => {
        btn.classList.remove('speaking');
        btn.querySelector('.speak-label').textContent = 'Listen';
        currentUtterance = null;
    };

    speechSynthesis.speak(utterance);
}

function stopSpeaking() {
    if ('speechSynthesis' in window) {
        speechSynthesis.cancel();
    }
    // Reset all speak buttons
    document.querySelectorAll('.btn-speak.speaking').forEach(btn => {
        btn.classList.remove('speaking');
        const label = btn.querySelector('.speak-label');
        if (label) label.textContent = 'Listen';
    });
    currentUtterance = null;
}

// Preload voices (needed for some browsers)
if ('speechSynthesis' in window) {
    speechSynthesis.getVoices();
    speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
}

// ---------------------------------------------------------------------------
// Speech-to-Text (STT) — Voice input from patient
// ---------------------------------------------------------------------------

function initRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return null;

    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = getSpeechLang();
    rec.maxAlternatives = 1;

    let finalTranscript = '';
    let interimTranscript = '';

    rec.onstart = () => {
        isRecording = true;
        finalTranscript = '';
        interimTranscript = '';
        document.getElementById('btn-mic').classList.add('recording');
        document.getElementById('voice-status').classList.add('active');
        document.getElementById('voice-status-text').textContent = 'Listening… speak now';
        document.getElementById('chat-input').placeholder = 'Listening…';
    };

    rec.onresult = (event) => {
        interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
            } else {
                interimTranscript += transcript;
            }
        }
        // Show transcription in the input field in real time
        const input = document.getElementById('chat-input');
        input.value = finalTranscript + interimTranscript;
        autoResize(input);
        document.getElementById('voice-status-text').textContent =
            interimTranscript ? 'Hearing you…' : 'Listening… speak now';
    };

    rec.onerror = (event) => {
        console.warn('Speech recognition error:', event.error);
        if (event.error === 'not-allowed') {
            alert('Microphone access was denied. Please allow microphone access in your browser settings to use voice input.');
        }
        stopRecording();
    };

    rec.onend = () => {
        // If still supposed to be recording (browser auto-stopped), the UI resets
        if (isRecording) {
            stopRecording();
        }
    };

    return rec;
}

function toggleVoiceInput() {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

function startRecording() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert('Voice input is not supported in your browser. Please use Chrome or Edge.');
        return;
    }

    // Stop any current speech output
    stopSpeaking();

    recognition = initRecognition();
    if (!recognition) return;

    // Set the correct language for this session
    recognition.lang = getSpeechLang();

    try {
        recognition.start();
    } catch (e) {
        console.error('Failed to start speech recognition:', e);
    }
}

function stopRecording() {
    isRecording = false;
    if (recognition) {
        try { recognition.stop(); } catch (e) { /* ignore */ }
        recognition = null;
    }
    document.getElementById('btn-mic').classList.remove('recording');
    document.getElementById('voice-status').classList.remove('active');
    document.getElementById('chat-input').placeholder = 'Type or tap the mic to speak…';
}

// ---------------------------------------------------------------------------
// Complete Session & Generate Summary
// ---------------------------------------------------------------------------

async function completeSession() {
    if (!state.currentSessionId) return;
    if (!confirm('End this session and generate summaries?')) return;

    stopSpeaking();
    stopRecording();
    showSpinner('Generating clinical summary & translating conversation…');

    try {
        const res = await fetch(`${API}/api/sessions/${state.currentSessionId}/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await res.json();

        document.getElementById('patient-summary-content').textContent =
            data.patient_summary || data.clinician_summary || 'Summary not available.';

        hideSpinner();
        showPatientStep('patient-summary');
    } catch (err) {
        hideSpinner();
        alert('Failed to generate summary. Please try again.');
        console.error(err);
    }
}

function backToRegister() {
    stopSpeaking();
    stopRecording();
    state.currentSessionId = null;
    state.currentPatientId = null;
    showPatientStep('patient-register');
}

// ---------------------------------------------------------------------------
// Doctor Portal — Session List
// ---------------------------------------------------------------------------

async function loadSessions() {
    const sortBy = document.getElementById('filter-sort')?.value || 'newest';
    const typeFilter = document.getElementById('filter-type')?.value || '';
    const statusFilter = document.getElementById('filter-status')?.value || '';
    const urgentOnly = document.getElementById('filter-urgent')?.value === 'urgent';

    try {
        const res = await fetch(`${API}/api/sessions`);
        let sessions = await res.json();

        if (typeFilter) sessions = sessions.filter(s => s.session_type === typeFilter);
        if (statusFilter) sessions = sessions.filter(s => s.status === statusFilter);
        if (urgentOnly) sessions = sessions.filter(s => s.is_urgent);

        // Sort: by name (A-Z / Z-A) or newest first
        const nameKey = (s) => (s.patient_name || '').toLowerCase();
        if (sortBy === 'name-az') {
            sessions = [...sessions].sort((a, b) => nameKey(a).localeCompare(nameKey(b)));
        } else if (sortBy === 'name-za') {
            sessions = [...sessions].sort((a, b) => nameKey(b).localeCompare(nameKey(a)));
        } else {
            sessions = [...sessions].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
        }

        const list = document.getElementById('session-list');
        if (sessions.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <p>No sessions found.</p>
                    <p class="text-muted">${urgentOnly ? 'No urgent sessions. Try "All" under Priority.' : 'Sessions will appear here once patients complete check-ins or follow-ups.'}</p>
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
                    <span class="badge ${s.session_type === 'pre' ? 'badge-pre' : 'badge-post'}">${s.session_type === 'pre' ? 'Pre' : 'Post'}</span>
                    <span class="badge ${s.status === 'completed' ? 'badge-success' : 'badge-warning'}">${s.status}</span>
                    <span>${s.language_used || ''}${s.dialect_used ? ' · ' + s.dialect_used : ''}</span>
                    <span>${formatDate(s.created_at)}</span>
                </div>
            </div>
        `).join('');
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
// Doctor Portal — Session Detail with Bilingual Transcript
// ---------------------------------------------------------------------------

async function loadSessionDetail(sessionId) {
    // Highlight active sidebar item
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
            <!-- Patient Info -->
            <div class="detail-section">
                <div class="detail-section-header">
                    <h3>Patient Information</h3>
                    <button type="button" class="btn ${s.is_urgent ? 'btn-outline' : 'btn-urgent'}" onclick="toggleSessionUrgent('${s.id}', ${!s.is_urgent})" id="btn-urgent-${s.id}">
                        ${s.is_urgent ? 'Unmark urgent' : 'Mark as URGENT'}
                    </button>
                </div>
                ${s.is_urgent ? '<p class="detail-urgent-banner"><strong>URGENT</strong> — Priority handling</p>' : ''}
                <div class="detail-meta">
                    <div class="meta-item">
                        <label>Patient Name</label>
                        <span>${escapeHtml(s.patient_name)}</span>
                    </div>
                    <div class="meta-item">
                        <label>Date of Birth</label>
                        <span>${s.patient_dob || '—'}</span>
                    </div>
                    <div class="meta-item">
                        <label>Session Type</label>
                        <span class="badge ${s.session_type === 'pre' ? 'badge-pre' : 'badge-post'}">${s.session_type === 'pre' ? 'Pre-Consultation' : 'Post-Consultation'}</span>
                    </div>
                    <div class="meta-item">
                        <label>Status</label>
                        <span class="badge ${s.status === 'completed' ? 'badge-success' : 'badge-warning'}">${s.status}</span>
                    </div>
                    <div class="meta-item">
                        <label>Language</label>
                        <span>${s.language_used}${s.dialect_used ? ' (' + s.dialect_used + ')' : ''}</span>
                    </div>
                    <div class="meta-item">
                        <label>Session Date</label>
                        <span>${formatDate(s.created_at)}</span>
                    </div>
                </div>
                ${s.patient_cultural_context ? `
                <div style="margin-top: var(--space-2);">
                    <label style="font-size: 0.75rem; color: var(--color-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 0.25rem;">Cultural Considerations</label>
                    <span style="font-size: 0.8125rem;">${escapeHtml(s.patient_cultural_context)}</span>
                </div>` : ''}
            </div>

            <!-- Clinical Summary -->
            ${s.clinician_summary ? `
            <div class="detail-section">
                <h3>Clinical Summary (English)</h3>
                <div class="clinician-summary-box">${formatSummaryHtml(s.clinician_summary)}</div>
            </div>` : ''}

            <!-- Patient Summary -->
            ${s.patient_summary ? `
            <div class="detail-section">
                <h3>Patient Summary (${escapeHtml(s.language_used)})</h3>
                <div class="patient-summary-box">${escapeHtml(s.patient_summary)}</div>
            </div>` : ''}

            <!-- Bilingual Conversation Transcript -->
            <div class="detail-section">
                <h3>Conversation Transcript ${!isEnglish && hasTranslations ? '— Bilingual View' : ''}</h3>
                ${!isEnglish && hasTranslations ? `<p style="font-size: 0.8125rem; color: var(--color-muted); margin-bottom: 1rem;">Original ${escapeHtml(s.language_used)} text shown alongside English translation for verification.</p>` : ''}
                <div class="transcript-bilingual">
                    ${s.messages.map(m => renderTranscriptMessage(m, s.language_used, isEnglish)).join('')}
                </div>
            </div>
        `;
    } catch (err) {
        console.error('Failed to load session detail', err);
    }
}

function renderTranscriptMessage(msg, language, isEnglish) {
    const isAssistant = msg.role === 'assistant';
    const speaker = isAssistant ? 'MedBridge (AI)' : 'Patient';
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
    const d = new Date(isoStr);
    return d.toLocaleDateString('en-SG', {
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
// Boot
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', init);
