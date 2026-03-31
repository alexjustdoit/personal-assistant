// --- Session management ---

function getSessionId() {
  let id = localStorage.getItem('active_session_id');
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem('active_session_id', id);
  }
  return id;
}

function newChat() {
  const id = crypto.randomUUID();
  localStorage.setItem('active_session_id', id);
  location.reload();
}

function switchChat(sessionId) {
  localStorage.setItem('active_session_id', sessionId);
  location.reload();
}

const SESSION_ID = getSessionId();
const WS_URL = `ws://${location.host}/ws/chat?session_id=${SESSION_ID}`;
let socket = null;
let isStreaming = false;

// --- DOM refs ---

const messagesEl = document.getElementById('messages');
const welcomeEl = document.getElementById('welcome');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send-btn');
const micBtn = document.getElementById('mic-btn');
const ttsToggle = document.getElementById('tts-toggle');
const statusDot = document.getElementById('status-dot');
const providerSelect = document.getElementById('provider-select');
const chatTitle = document.getElementById('chat-title');
const chatListEl = document.getElementById('chat-list');
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebar = document.getElementById('sidebar');
const sidebarBackdrop = document.getElementById('sidebar-backdrop');
const newChatBtn = document.getElementById('new-chat-btn');

// --- Sidebar ---

let sidebarOpen = window.innerWidth >= 1024;

function setSidebar(open) {
  sidebarOpen = open;
  if (open) {
    sidebar.classList.remove('sidebar-hidden');
    sidebar.classList.add('sidebar-visible');
  } else {
    sidebar.classList.remove('sidebar-visible');
    sidebar.classList.add('sidebar-hidden');
  }
  if (open && window.innerWidth < 1024) {
    sidebarBackdrop.classList.remove('hidden');
  } else {
    sidebarBackdrop.classList.add('hidden');
  }
}

sidebarToggle.addEventListener('click', () => setSidebar(!sidebarOpen));
sidebarBackdrop.addEventListener('click', () => setSidebar(false));
newChatBtn.addEventListener('click', newChat);

setSidebar(sidebarOpen);

// --- Chat list ---

function formatRelativeTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString + (isoString.endsWith('Z') ? '' : 'Z'));
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return 'yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

async function loadChatList() {
  try {
    const res = await fetch('/api/chats');
    const data = await res.json();
    const chats = data.chats || [];

    chatListEl.innerHTML = '';

    if (chats.length === 0) {
      chatListEl.innerHTML = '<p class="text-gray-600 text-xs px-4 py-3">No previous chats</p>';
      return;
    }

    for (const chat of chats) {
      const isActive = chat.id === SESSION_ID;
      const btn = document.createElement('button');
      btn.className = `chat-list-item w-full text-left px-3 py-2.5 mx-1 rounded-lg transition-colors ${
        isActive
          ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-600/30'
          : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
      }`;

      const name = document.createElement('div');
      name.className = 'truncate text-sm font-medium';
      name.textContent = chat.name || 'New chat';

      const time = document.createElement('div');
      time.className = 'text-xs mt-0.5 opacity-50 truncate';
      time.textContent = formatRelativeTime(chat.last_active);

      btn.appendChild(name);
      btn.appendChild(time);

      if (!isActive) {
        btn.addEventListener('click', () => switchChat(chat.id));
      }

      chatListEl.appendChild(btn);

      if (isActive && chat.name) {
        chatTitle.textContent = chat.name;
      }
    }
  } catch {
    chatListEl.innerHTML = '<p class="text-gray-600 text-xs px-4 py-3">Failed to load chats</p>';
  }
}

// --- WebSocket ---

function connect() {
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    statusDot.classList.replace('bg-red-500', 'bg-green-500');
    statusDot.classList.add('bg-green-500');
  };

  socket.onclose = () => {
    statusDot.classList.replace('bg-green-500', 'bg-red-500');
    setTimeout(connect, 3000);
  };

  socket.onerror = () => {
    statusDot.classList.replace('bg-green-500', 'bg-red-500');
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'token') {
      appendToken(data.content);
    } else if (data.type === 'done') {
      finishStreaming();
      loadChatList(); // refresh names after first assistant reply
    } else if (data.type === 'error') {
      finishStreaming();
      appendError(data.content);
    }
  };
}

// --- Chat UI ---

function showMessages() {
  if (!welcomeEl.classList.contains('hidden')) {
    welcomeEl.classList.add('hidden');
    messagesEl.classList.remove('hidden');
  }
}

function appendMessage(role, content = '') {
  showMessages();
  const wrapper = document.createElement('div');
  wrapper.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'}`;

  const bubble = document.createElement('div');
  bubble.className = role === 'user'
    ? 'max-w-xl bg-indigo-600 text-white px-4 py-3 rounded-2xl rounded-tr-sm text-sm'
    : 'max-w-xl bg-gray-800 text-gray-100 px-4 py-3 rounded-2xl rounded-tl-sm text-sm message-content';

  bubble.textContent = content;
  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  return bubble;
}

let currentBubble = null;
let currentText = '';

function startAssistantBubble() {
  currentText = '';
  currentBubble = appendMessage('assistant');
  currentBubble.classList.add('streaming');
}

function appendToken(token) {
  if (!currentBubble) startAssistantBubble();
  currentText += token;
  currentBubble.textContent = currentText;
  messagesEl.scrollTop = messagesEl.scrollHeight;
  if (ttsEnabled) processTTSToken(token);
}

function finishStreaming() {
  if (currentBubble) {
    currentBubble.classList.remove('streaming');
    currentBubble = null;
    currentText = '';
  }
  if (ttsEnabled) flushTTSBuffer();
  isStreaming = false;
  setInputEnabled(true);
}

function appendError(message) {
  const wrapper = document.createElement('div');
  wrapper.className = 'flex justify-start';
  const bubble = document.createElement('div');
  bubble.className = 'max-w-xl bg-red-900 text-red-200 px-4 py-3 rounded-2xl text-sm';
  bubble.textContent = `Error: ${message}`;
  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setInputEnabled(enabled) {
  inputEl.disabled = !enabled;
  sendBtn.disabled = !enabled;
  micBtn.disabled = !enabled;
  if (enabled) inputEl.focus();
}

function sendMessage() {
  const content = inputEl.value.trim();
  if (!content || isStreaming || !socket || socket.readyState !== WebSocket.OPEN) return;

  appendMessage('user', content);
  inputEl.value = '';
  isStreaming = true;
  resetTTS();
  setInputEnabled(false);
  startAssistantBubble();

  socket.send(JSON.stringify({ type: 'message', content, provider: providerSelect.value }));
}

sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// --- Voice input (STT) ---

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
      await transcribeAudio(blob);
    };

    mediaRecorder.start();
    isRecording = true;
    micBtn.textContent = '⏹️';
    micBtn.classList.add('recording');
  } catch {
    appendError('Microphone access denied or unavailable');
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
    micBtn.textContent = '🎤';
    micBtn.classList.remove('recording');
  }
}

async function transcribeAudio(blob) {
  micBtn.textContent = '⏳';
  micBtn.disabled = true;
  try {
    const formData = new FormData();
    formData.append('audio', blob, 'recording.webm');
    const res = await fetch('/api/voice/transcribe', { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    if (data.text) {
      inputEl.value = data.text;
      sendMessage();
    }
  } catch (err) {
    appendError(`Transcription failed: ${err.message}`);
  } finally {
    micBtn.textContent = '🎤';
    micBtn.disabled = false;
  }
}

micBtn.addEventListener('click', () => {
  if (isRecording) stopRecording();
  else startRecording();
});

// --- TTS (sentence-level streaming) ---

let ttsEnabled = false;
let ttsQueue = [];
let ttsPlaying = false;
let ttsSentenceBuffer = '';
let ttsCurrentAudio = null;

const SENTENCE_END = /[.!?]+\s/;

function processTTSToken(token) {
  ttsSentenceBuffer += token;
  const match = SENTENCE_END.exec(ttsSentenceBuffer);
  if (match) {
    const cutAt = match.index + match[0].length;
    const sentence = ttsSentenceBuffer.slice(0, cutAt).trim();
    ttsSentenceBuffer = ttsSentenceBuffer.slice(cutAt);
    if (sentence) enqueueTTS(sentence);
  }
}

function flushTTSBuffer() {
  const remaining = ttsSentenceBuffer.trim();
  ttsSentenceBuffer = '';
  if (remaining) enqueueTTS(remaining);
}

function resetTTS() {
  ttsQueue = [];
  ttsSentenceBuffer = '';
  if (ttsCurrentAudio) {
    ttsCurrentAudio.pause();
    ttsCurrentAudio = null;
  }
  ttsPlaying = false;
}

function enqueueTTS(text) {
  ttsQueue.push(text);
  if (!ttsPlaying) playNextTTS();
}

async function playNextTTS() {
  if (ttsQueue.length === 0) { ttsPlaying = false; return; }
  ttsPlaying = true;
  const text = ttsQueue.shift();
  try {
    const res = await fetch('/api/voice/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) { playNextTTS(); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    ttsCurrentAudio = new Audio(url);
    ttsCurrentAudio.onended = () => {
      URL.revokeObjectURL(url);
      ttsCurrentAudio = null;
      playNextTTS();
    };
    ttsCurrentAudio.play();
  } catch {
    playNextTTS();
  }
}

function setTTS(enabled) {
  ttsEnabled = enabled;
  ttsToggle.textContent = enabled ? '🔊' : '🔇';
  ttsToggle.title = enabled ? 'Voice responses on' : 'Voice responses off';
}

ttsToggle.addEventListener('click', () => setTTS(!ttsEnabled));

// --- Init ---

async function loadProviders() {
  try {
    const res = await fetch('/api/providers');
    const data = await res.json();
    providerSelect.innerHTML = '';
    for (const p of data.providers) {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.label;
      if (p.id === data.default) opt.selected = true;
      providerSelect.appendChild(opt);
    }
  } catch {
    providerSelect.innerHTML = '<option value="ollama">Ollama</option>';
  }
}

async function initVoice() {
  try {
    const res = await fetch('/api/voice/status');
    const data = await res.json();
    if (!data.stt) micBtn.style.display = 'none';
    if (data.tts) setTTS(true);
    if (!data.tts) ttsToggle.style.display = 'none';
  } catch {
    micBtn.style.display = 'none';
    ttsToggle.style.display = 'none';
  }
}

async function loadHistory() {
  try {
    const res = await fetch(`/api/history/${SESSION_ID}`);
    const data = await res.json();
    if (data.messages && data.messages.length > 0) {
      for (const msg of data.messages) {
        appendMessage(msg.role, msg.content);
      }
    }
  } catch {
    // non-fatal
  }
}

document.querySelectorAll('.suggestion-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    inputEl.value = chip.dataset.prompt;
    sendMessage();
  });
});

connect();
loadProviders();
initVoice();
loadHistory();
loadChatList();
