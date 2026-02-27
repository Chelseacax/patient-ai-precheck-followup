/* ==========================================================================
   MedBridge — Frontend Application Logic
   Voice AI Pre-Consultation Check-In + Doctor Portal
   ========================================================================== */

const API = '';  // Same origin

// ---------------------------------------------------------------------------
// Speech language mapping (our language code → BCP 47 for Web Speech API)
// ---------------------------------------------------------------------------

const SPEECH_LANG_MAP = {
    'en':            'en-SG',
    'zh':            'zh-CN',
    'ms':            'ms-MY',
    'ta':            'ta-SG',
    'zh-hokkien':    'zh-CN',
    'zh-teochew':    'zh-CN',
    'zh-cantonese':  'zh-HK',
    'zh-hakka':      'zh-CN',
    'zh-hainanese':  'zh-CN',
    'hi':            'hi-IN',
    'tl':            'fil-PH',
    'vi':            'vi-VN',
    'th':            'th-TH',
    'id':            'id-ID',
    'my':            'my-MM',
    'bn':            'bn-BD',
    'km':            'km-KH',
    'lo':            'lo-LA',
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let state = {
    languages: {},
    currentView: 'home',
};

// Voice check-in state
let checkinState = {
    patientId: null,
    sessionId: null,
    langCode: 'en',       // BCP-47 base code
    langName: 'English',
    isAutoMode: true,     // auto speak→listen→send loop
    isSpeaking: false,
    isListening: false,
};

let checkinRec = null;        // active SpeechRecognition for check-in
let checkinUtterance = null;  // active TTS utterance for check-in

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
    if (view === 'booking') showBookingStep('booking-setup');

    stopCheckinSpeaking();
    stopCheckinVoice();
    stopBookingSpeaking();
    stopBookingVoice();
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
        populateBookingLanguageDropdown();
    } catch (e) {
        console.error('Failed to load languages', e);
    }
    checkApiKey();
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
                    '<strong>Your API key is invalid or expired.</strong> Please enter a valid MERaLion, OpenAI (sk-...), or Groq (gsk_...) API key.';
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
    if (!key) { alert('Please enter an API key (MERaLion, OpenAI sk-..., or Groq gsk_...).'); return; }

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
    const langs = Object.keys(state.languages);
    const groups = [
        { label: 'Singapore Official Languages', items: langs.slice(0, 4) },
        { label: 'Singapore Chinese Dialects',   items: langs.slice(4, 9) },
        { label: 'Southeast Asian Languages',    items: langs.slice(9) },
    ];
    for (const group of groups) {
        if (!group.items.length) continue;
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
    updateCheckinDialects();
}

function updateCheckinDialects() {
    const lang = document.getElementById('checkin-language').value;
    const sel = document.getElementById('checkin-dialect');
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
// Check-In — Setup & Session Start
// ---------------------------------------------------------------------------

async function handleCheckinSetup(e) {
    e.preventDefault();
    const name     = document.getElementById('checkin-name').value.trim();
    const dob      = document.getElementById('checkin-dob').value;
    const language = document.getElementById('checkin-language').value;
    const dialect  = document.getElementById('checkin-dialect').value;
    const cultural = document.getElementById('checkin-cultural').value.trim();

    const langData = state.languages[language];
    checkinState.langCode = langData?.code || 'en';
    checkinState.langName = language;
    checkinState.isAutoMode = true;

    showSpinner('Starting your check-in with Aria…');

    try {
        // Create patient record
        const pRes = await fetch(`${API}/api/patients`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, date_of_birth: dob, preferred_language: language, dialect, cultural_context: cultural }),
        });
        const patient = await pRes.json();
        checkinState.patientId = patient.id;

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

        // Set up chat UI
        document.getElementById('checkin-messages').innerHTML = '';
        document.getElementById('checkin-input').value = '';
        document.getElementById('checkin-chat-title').textContent = name;
        document.getElementById('checkin-lang-badge').textContent =
            `${language}${dialect ? ' · ' + dialect : ''}`;
        updateAutoModeUI();

        hideSpinner();
        showCheckinStep('checkin-chat');

        // Greet and start voice loop
        appendCheckinBubble('assistant', session.greeting);
        if (checkinState.isAutoMode) {
            checkinSpeakThenListen(session.greeting);
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
    showCheckinStep('checkin-setup');
}

// ---------------------------------------------------------------------------
// Check-In — Chat Messaging
// ---------------------------------------------------------------------------

async function sendCheckinMessage(textOverride) {
    const input = document.getElementById('checkin-input');
    const text = (textOverride !== undefined ? textOverride : input.value).trim();
    if (!text || !checkinState.sessionId) return;

    input.value = '';
    input.style.height = 'auto';
    appendCheckinBubble('user', text);
    showCheckinTyping();

    document.getElementById('btn-checkin-send').disabled = true;
    document.getElementById('btn-send-to-doctor').disabled = true;

    try {
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
    if (!('speechSynthesis' in window)) return;
    stopCheckinSpeaking();
    stopCheckinVoice();

    setCheckinVoiceIndicator('speaking');

    const utterance = new SpeechSynthesisUtterance(text);
    const bcp47 = SPEECH_LANG_MAP[checkinState.langCode] || 'en-SG';
    utterance.lang = bcp47;
    utterance.rate = 0.92;
    utterance.pitch = 1;

    // Try to pick a matching voice
    const voices = speechSynthesis.getVoices();
    const matched = voices.find(v => v.lang === bcp47) ||
                    voices.find(v => v.lang.startsWith(bcp47.split('-')[0]));
    if (matched) utterance.voice = matched;

    checkinUtterance = utterance;
    checkinState.isSpeaking = true;

    utterance.onend = () => {
        checkinState.isSpeaking = false;
        checkinUtterance = null;
        if (checkinState.isAutoMode) {
            setCheckinVoiceIndicator('idle');
            setTimeout(() => startCheckinListening(), 400);
        } else {
            setCheckinVoiceIndicator('idle');
        }
    };
    utterance.onerror = () => {
        checkinState.isSpeaking = false;
        checkinUtterance = null;
        setCheckinVoiceIndicator('idle');
    };

    speechSynthesis.speak(utterance);
}

function stopCheckinSpeaking() {
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    checkinState.isSpeaking = false;
    checkinUtterance = null;
}

// Preload voices (needed for some browsers)
if ('speechSynthesis' in window) {
    speechSynthesis.getVoices();
    speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
}

// ---------------------------------------------------------------------------
// Check-In — STT (Speech-to-Text)
// ---------------------------------------------------------------------------

function startCheckinListening() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition || checkinState.isListening) return;

    stopCheckinVoice();

    const rec = new SpeechRecognition();
    rec.continuous = false;   // auto-stops on silence → onend fires → sends message
    rec.interimResults = true;
    rec.lang = SPEECH_LANG_MAP[checkinState.langCode] || 'en-SG';

    checkinState.isListening = true;
    checkinRec = rec;

    setCheckinVoiceIndicator('listening');
    document.getElementById('btn-checkin-mic').classList.add('recording');
    document.getElementById('checkin-voice-status').classList.add('active');

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
        console.warn('Check-in STT error:', event.error);
        if (event.error === 'not-allowed') {
            alert('Microphone access was denied. Please allow microphone access to use voice input.');
        }
        checkinState.isListening = false;
        checkinRec = null;
        document.getElementById('btn-checkin-mic').classList.remove('recording');
        document.getElementById('checkin-voice-status').classList.remove('active');
        setCheckinVoiceIndicator('idle');
    };

    try { rec.start(); } catch (e) { console.error('STT start error:', e); }
}

function stopCheckinVoice() {
    checkinState.isListening = false;
    if (checkinRec) {
        try { checkinRec.stop(); } catch (e) { /* ignore */ }
        checkinRec = null;
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
// Booking Agent — State
// ---------------------------------------------------------------------------

let bookingState = {
    patientId: null,
    bookingSessionId: null,
    langCode: 'en',
    langName: 'English',
    isAutoMode: true,
    isSpeaking: false,
    isListening: false,
    selectedSlotId: null,
};

let bookingRec = null;
let bookingUtterance = null;

// ---------------------------------------------------------------------------
// Booking Agent — Language Dropdowns
// ---------------------------------------------------------------------------

function populateBookingLanguageDropdown() {
    const sel = document.getElementById('booking-language');
    if (!sel) return;
    sel.innerHTML = '';
    Object.keys(state.languages).forEach(lang => {
        const opt = document.createElement('option');
        opt.value = lang;
        opt.textContent = lang;
        if (lang === 'English') opt.selected = true;
        sel.appendChild(opt);
    });
    updateBookingDialects();
}

function updateBookingDialects() {
    const lang = document.getElementById('booking-language').value;
    const dialectSel = document.getElementById('booking-dialect');
    dialectSel.innerHTML = '<option value="">— Select —</option>';
    const dialects = (state.languages[lang] || {}).dialects || [];
    dialects.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = d;
        dialectSel.appendChild(opt);
    });
    bookingState.langCode = (state.languages[lang] || {}).code || 'en';
    bookingState.langName = lang;
}

// ---------------------------------------------------------------------------
// Booking Agent — Setup
// ---------------------------------------------------------------------------

async function handleBookingSetup(event) {
    event.preventDefault();
    const name     = document.getElementById('booking-name').value.trim();
    const language = document.getElementById('booking-language').value;
    const dialect  = document.getElementById('booking-dialect').value;

    if (!name) { alert('Please enter your name.'); return; }

    const btn = document.getElementById('btn-start-booking');
    btn.disabled = true;
    btn.textContent = 'Starting…';

    try {
        const res = await fetch(`${API}/api/booking/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, language, dialect }),
        });
        const data = await res.json();
        if (!res.ok) { alert(data.error || 'Failed to start booking.'); return; }

        bookingState.patientId       = data.patient_id;
        bookingState.bookingSessionId = data.booking_session_id;
        bookingState.langName        = language;
        bookingState.langCode        = (state.languages[language] || {}).code || 'en';

        document.getElementById('booking-chat-title').textContent = `Aria — ${escapeHtml(data.patient_name)}`;
        document.getElementById('booking-lang-badge').textContent = language + (dialect ? ` · ${dialect}` : '');
        document.getElementById('booking-messages').innerHTML = '';
        document.getElementById('booking-state-card').classList.add('hidden');

        showBookingStep('booking-chat');
        appendBookingBubble('assistant', data.welcome_message);
        bookingSpeakThenListen(data.welcome_message);

    } catch (err) {
        alert('Failed to start booking. Please check your connection.');
        console.error(err);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg> Start Voice Booking';
    }
}

function showBookingStep(stepId) {
    // Only toggle steps within view-booking
    document.querySelectorAll('#view-booking .checkin-step').forEach(s => s.classList.remove('active'));
    document.getElementById(stepId).classList.add('active');
}

function backToBookingSetup() {
    stopBookingSpeaking();
    stopBookingVoice();
    showBookingStep('booking-setup');
}

// ---------------------------------------------------------------------------
// Booking Agent — Send Message
// ---------------------------------------------------------------------------

async function sendBookingMessage(overrideText) {
    const input = document.getElementById('booking-input');
    const text = (overrideText !== undefined ? overrideText : input.value).trim();
    if (!text || !bookingState.bookingSessionId) return;

    input.value = '';
    input.style.height = '';
    stopBookingVoice();

    appendBookingBubble('user', text);
    setBookingStatus('Processing…');

    try {
        const res = await fetch(`${API}/api/booking/${bookingState.bookingSessionId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });
        const data = await res.json();

        appendBookingBubble('assistant', data.response_text);
        renderBookingStateCard(data);

        if (data.state === 'confirmed') {
            showBookingConfirmed(data);
            return;
        }
        if (data.state === 'cancelled') {
            appendBookingBubble('assistant', 'Your booking has been cancelled. Feel free to start a new one.');
            return;
        }

        bookingSpeakThenListen(data.response_text);

    } catch (err) {
        appendBookingBubble('assistant', '[Error communicating with server. Please try again.]');
        console.error(err);
    }
}

function handleBookingKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendBookingMessage();
    }
}

// ---------------------------------------------------------------------------
// Booking Agent — State Card
// ---------------------------------------------------------------------------

function renderBookingStateCard(data) {
    const card = document.getElementById('booking-state-card');

    // Show normalized input
    const normalizedRow = document.getElementById('booking-normalized-row');
    const normalizedText = document.getElementById('booking-normalized-text');
    if (data.normalized_input) {
        normalizedText.textContent = data.normalized_input;
        normalizedRow.classList.remove('hidden');
    } else {
        normalizedRow.classList.add('hidden');
    }

    // Show available slots
    const slotsList = document.getElementById('booking-slots-list');
    slotsList.innerHTML = '';
    bookingState.selectedSlotId = null;

    if (data.available_slots && data.available_slots.length > 0) {
        data.available_slots.forEach((slot, i) => {
            const item = document.createElement('div');
            item.className = 'booking-slot-item' + (i === 0 ? ' selected' : '');
            if (i === 0) bookingState.selectedSlotId = slot.id;
            item.innerHTML = `
                <div>
                    <div class="booking-slot-doctor">${escapeHtml(slot.doctor_name)}</div>
                    <div class="booking-slot-specialty">${escapeHtml(slot.specialty)}</div>
                </div>
                <div class="booking-slot-datetime">
                    <div>${escapeHtml(slot.slot_date)}</div>
                    <div>${escapeHtml(slot.slot_time)}</div>
                </div>`;
            item.onclick = () => {
                document.querySelectorAll('.booking-slot-item').forEach(el => el.classList.remove('selected'));
                item.classList.add('selected');
                bookingState.selectedSlotId = slot.id;
            };
            slotsList.appendChild(item);
        });
        card.classList.remove('hidden');
    }

    // Show confirm/cancel buttons when confirming
    const confirmActions = document.getElementById('booking-confirm-actions');
    if (data.requires_confirmation) {
        confirmActions.classList.remove('hidden');
        card.classList.remove('hidden');
    } else {
        confirmActions.classList.add('hidden');
    }

    if (!data.normalized_input && (!data.available_slots || data.available_slots.length === 0)) {
        card.classList.add('hidden');
    }
}

// ---------------------------------------------------------------------------
// Booking Agent — Confirm / Cancel
// ---------------------------------------------------------------------------

async function confirmBooking() {
    if (!bookingState.bookingSessionId) return;
    try {
        const res = await fetch(`${API}/api/booking/${bookingState.bookingSessionId}/confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await res.json();
        if (!res.ok) { alert(data.error || 'Failed to confirm booking.'); return; }
        showBookingConfirmed(data);
    } catch (err) {
        alert('Failed to confirm booking. Please try again.');
        console.error(err);
    }
}

async function cancelBookingSession() {
    if (!bookingState.bookingSessionId) return;
    await fetch(`${API}/api/booking/${bookingState.bookingSessionId}/cancel`, { method: 'POST' });
    document.getElementById('booking-state-card').classList.add('hidden');
    appendBookingBubble('assistant', 'Booking cancelled. Let me know if you\'d like to try again.');
    bookingSpeakThenListen('Booking cancelled. Let me know if you\'d like to try again with different preferences.');
}

function showBookingConfirmed(data) {
    stopBookingSpeaking();
    stopBookingVoice();

    const ref = data.booking_ref || '';
    const details = document.getElementById('booking-confirmed-details');
    details.innerHTML = `
        <div class="booking-ref">${escapeHtml(ref)}</div>
        <div class="detail-row"><span class="detail-label">Doctor</span><span class="detail-value">${escapeHtml(data.doctor_name || '')}</span></div>
        <div class="detail-row"><span class="detail-label">Specialty</span><span class="detail-value">${escapeHtml(data.specialty || '')}</span></div>
        <div class="detail-row"><span class="detail-label">Date</span><span class="detail-value">${escapeHtml(data.slot_date || '')}</span></div>
        <div class="detail-row"><span class="detail-label">Time</span><span class="detail-value">${escapeHtml(data.slot_time || '')}</span></div>`;

    showBookingStep('booking-confirmed');

    const msg = `Your appointment has been confirmed. Your booking reference is ${ref}. See you at ${data.slot_time} on ${data.slot_date}.`;
    bookingSpeakThenListen(msg);
}

// ---------------------------------------------------------------------------
// Booking Agent — Voice (TTS + STT)
// ---------------------------------------------------------------------------

function bookingSpeakThenListen(text) {
    stopBookingSpeaking();
    const indicator = document.getElementById('booking-voice-indicator');
    const statusText = document.getElementById('booking-voice-status-text');

    if (!window.speechSynthesis) {
        setBookingStatus('Ready');
        if (bookingState.isAutoMode) setTimeout(startBookingListening, 400);
        return;
    }

    bookingUtterance = new SpeechSynthesisUtterance(text);
    const bcp47 = SPEECH_LANG_MAP[bookingState.langCode] || 'en-SG';
    bookingUtterance.lang = bcp47;
    bookingUtterance.rate = 0.9;

    const voices = window.speechSynthesis.getVoices();
    const match = voices.find(v => v.lang.startsWith(bcp47.split('-')[0]));
    if (match) bookingUtterance.voice = match;

    bookingUtterance.onstart = () => {
        bookingState.isSpeaking = true;
        indicator.classList.remove('hidden');
        statusText.textContent = 'Aria is speaking…';
        setBookingStatus('Speaking…');
    };
    bookingUtterance.onend = () => {
        bookingState.isSpeaking = false;
        indicator.classList.add('hidden');
        if (bookingState.isAutoMode) setTimeout(startBookingListening, 400);
    };
    bookingUtterance.onerror = () => {
        bookingState.isSpeaking = false;
        indicator.classList.add('hidden');
    };

    window.speechSynthesis.speak(bookingUtterance);
}

function stopBookingSpeaking() {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    bookingState.isSpeaking = false;
    const indicator = document.getElementById('booking-voice-indicator');
    if (indicator) indicator.classList.add('hidden');
}

function startBookingListening() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { setBookingStatus('Voice not supported in this browser.'); return; }
    if (bookingState.isListening) return;

    stopBookingVoice();

    const bcp47 = SPEECH_LANG_MAP[bookingState.langCode] || 'en-SG';
    bookingRec = new SpeechRecognition();
    bookingRec.lang = bcp47;
    bookingRec.continuous = false;
    bookingRec.interimResults = true;

    const indicator = document.getElementById('booking-voice-indicator');
    const statusText = document.getElementById('booking-voice-status-text');
    const input = document.getElementById('booking-input');
    let finalTranscript = '';

    bookingRec.onstart = () => {
        bookingState.isListening = true;
        indicator.classList.remove('hidden');
        statusText.textContent = 'Listening…';
        setBookingStatus('Listening…');
        document.getElementById('btn-booking-mic').classList.add('active');
    };
    bookingRec.onresult = (e) => {
        let interim = '';
        finalTranscript = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
            if (e.results[i].isFinal) finalTranscript += e.results[i][0].transcript;
            else interim += e.results[i][0].transcript;
        }
        input.value = finalTranscript || interim;
    };
    bookingRec.onend = () => {
        bookingState.isListening = false;
        indicator.classList.add('hidden');
        setBookingStatus('Ready');
        document.getElementById('btn-booking-mic').classList.remove('active');
        if (bookingState.isAutoMode && finalTranscript.trim()) {
            setTimeout(() => sendBookingMessage(finalTranscript.trim()), 300);
        }
    };
    bookingRec.onerror = (e) => {
        bookingState.isListening = false;
        indicator.classList.add('hidden');
        document.getElementById('btn-booking-mic').classList.remove('active');
        if (e.error === 'not-allowed') alert('Microphone access denied. Please allow microphone access.');
    };

    bookingRec.start();
}

function stopBookingVoice() {
    if (bookingRec) { try { bookingRec.stop(); } catch (_) {} bookingRec = null; }
    bookingState.isListening = false;
    const indicator = document.getElementById('booking-voice-indicator');
    if (indicator) indicator.classList.add('hidden');
    const btn = document.getElementById('btn-booking-mic');
    if (btn) btn.classList.remove('active');
}

function toggleBookingVoice() {
    if (bookingState.isListening) stopBookingVoice();
    else startBookingListening();
}

function toggleBookingAutoMode() {
    bookingState.isAutoMode = !bookingState.isAutoMode;
    document.getElementById('booking-auto-mode-label').textContent =
        bookingState.isAutoMode ? 'Auto On' : 'Auto Off';
}

// ---------------------------------------------------------------------------
// Booking Agent — UI helpers
// ---------------------------------------------------------------------------

function appendBookingBubble(role, text) {
    const container = document.getElementById('booking-messages');
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${role === 'user' ? 'user-bubble' : 'assistant-bubble'}`;
    bubble.innerHTML = `<div class="message-content">${escapeHtml(text)}</div>`;
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
}

function setBookingStatus(text) {
    const el = document.getElementById('booking-status-text');
    if (el) el.textContent = text;
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', init);
