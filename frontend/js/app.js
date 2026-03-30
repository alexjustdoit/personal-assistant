const messagesEl = document.getElementById('messages');
const welcomeEl = document.getElementById('welcome');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send-btn');
const micBtn = document.getElementById('mic-btn');
const ttsToggle = document.getElementById('tts-toggle');
const statusDot = document.getElementById('status-dot');
const providerSelect = document.getElementById('provider-select');

const WS_URL = `ws://${location.host}/ws/chat`;
let socket = null;
let isStreaming = false;

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
}

function finishStreaming() {
  if (currentBubble) {
    currentBubble.classList.remove('streaming');
    const textToSpeak = currentText;
    currentBubble = null;
    currentText = '';
    if (ttsEnabled) speakText(textToSpeak);
  }
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
  } catch (err) {
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
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

// --- TTS ---

let ttsEnabled = false;

function setTTS(enabled) {
  ttsEnabled = enabled;
  ttsToggle.textContent = enabled ? '🔊' : '🔇';
  ttsToggle.title = enabled ? 'Voice responses on' : 'Voice responses off';
}

ttsToggle.addEventListener('click', () => setTTS(!ttsEnabled));

async function speakText(text) {
  try {
    const res = await fetch('/api/voice/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
    audio.onended = () => URL.revokeObjectURL(url);
  } catch {
    // TTS failure is non-fatal — message is already displayed as text
  }
}

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
    if (data.tts) setTTS(true);  // default on if TTS is available
    if (!data.tts) ttsToggle.style.display = 'none';
  } catch {
    micBtn.style.display = 'none';
    ttsToggle.style.display = 'none';
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
