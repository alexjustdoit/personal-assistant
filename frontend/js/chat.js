// --- Session management ---

function getSessionId() {
  let id = localStorage.getItem('active_session_id');
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem('active_session_id', id);
  }
  return id;
}

let SESSION_ID = getSessionId();
let socket = null;
let isStreaming = false;

function switchToSession(id) {
  if (isStreaming) {
    if (!confirm('A response is in progress and will be lost. Switch anyway?')) return;
  }
  // Close existing socket without triggering auto-reconnect
  if (socket) {
    socket.onclose = null;
    socket.close();
    socket = null;
  }
  SESSION_ID = id;
  localStorage.setItem('active_session_id', id);
  isStreaming = false;
  currentBubble = null;
  currentText = '';
  messagesEl.innerHTML = '';
  welcomeEl.classList.remove('hidden');
  messagesEl.classList.add('hidden');
  chatTitle.textContent = 'Personal Assistant';
  resetTTS();
  setInputEnabled(true);
  loadHistory();
  connect();
  loadChatList();
}

function newChat() {
  switchToSession(crypto.randomUUID());
}

function switchChat(sessionId) {
  if (sessionId === SESSION_ID) return;
  switchToSession(sessionId);
}

// --- DOM refs ---

// Configure marked
marked.use({ breaks: true, gfm: true });

const messagesEl = document.getElementById('messages');
const welcomeEl = document.getElementById('welcome');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send-btn');
const stopBtn = document.getElementById('stop-btn');
const exportBtn = document.getElementById('export-btn');
const micBtn = document.getElementById('mic-btn');
const ttsToggle = document.getElementById('tts-toggle');
const statusDot = document.getElementById('status-dot');
const providerSelect = document.getElementById('provider-select');
const chatTitle = document.getElementById('chat-title');
const chatListEl = document.getElementById('chat-list');
const chatSearchEl = document.getElementById('chat-search');
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebar = document.getElementById('sidebar');
const sidebarBackdrop = document.getElementById('sidebar-backdrop');
const newChatBtn = document.getElementById('new-chat-btn');
const imageBtn = document.getElementById('image-btn');
const imageInput = document.getElementById('image-input');
const imagePreviewArea = document.getElementById('image-preview-area');
const imagePreviewEl = document.getElementById('image-preview');
const imageRemoveBtn = document.getElementById('image-remove');

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

function buildChatItem(chat) {
  const isActive = chat.id === SESSION_ID;
  const item = document.createElement('div');
  item.className = `group relative flex items-center mx-1 rounded-lg ${
    isActive ? 'bg-indigo-600/20 border border-indigo-600/30' : 'hover:bg-gray-800'
  }`;

  const btn = document.createElement('button');
  btn.className = `flex-1 text-left px-3 py-2.5 rounded-lg transition-colors min-w-0 ${
    isActive ? 'text-indigo-300' : 'text-gray-400 hover:text-gray-200'
  }`;

  const nameEl = document.createElement('div');
  nameEl.className = 'truncate text-sm font-medium';
  nameEl.textContent = chat.name || 'New chat';

  const timeEl = document.createElement('div');
  timeEl.className = 'text-xs mt-0.5 opacity-50 truncate';
  timeEl.textContent = formatRelativeTime(chat.last_active);

  btn.appendChild(nameEl);
  btn.appendChild(timeEl);
  if (!isActive) btn.addEventListener('click', () => switchChat(chat.id));

  // Rename + delete actions — revealed on hover
  const actions = document.createElement('div');
  actions.className = 'flex items-center gap-0.5 pr-1.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0';

  const renameBtn = document.createElement('button');
  renameBtn.className = 'p-1 text-gray-600 hover:text-gray-400 rounded transition-colors';
  renameBtn.title = 'Rename';
  renameBtn.innerHTML = `<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>`;
  renameBtn.addEventListener('click', (e) => { e.stopPropagation(); startInlineRename(chat, nameEl); });

  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'p-1 text-gray-600 hover:text-red-400 rounded transition-colors';
  deleteBtn.title = 'Delete chat';
  deleteBtn.innerHTML = `<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>`;
  deleteBtn.addEventListener('click', (e) => { e.stopPropagation(); deleteChatById(chat.id, isActive); });

  actions.appendChild(renameBtn);
  actions.appendChild(deleteBtn);
  item.appendChild(btn);
  item.appendChild(actions);
  return item;
}

function startInlineRename(chat, nameEl) {
  const original = nameEl.textContent;
  const input = document.createElement('input');
  input.type = 'text';
  input.value = original;
  input.className = 'text-sm font-medium bg-gray-700 text-gray-100 rounded px-1 py-0 w-full focus:outline-none focus:ring-1 focus:ring-indigo-500 min-w-0';
  nameEl.replaceWith(input);
  input.focus();
  input.select();

  async function save() {
    const name = input.value.trim();
    const newNameEl = document.createElement('div');
    newNameEl.className = 'truncate text-sm font-medium';
    newNameEl.textContent = name || original;
    input.replaceWith(newNameEl);
    if (name && name !== original) {
      await fetch(`/api/chats/${chat.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (chat.id === SESSION_ID) chatTitle.textContent = name;
      loadChatList();
    }
  }

  input.addEventListener('blur', save);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    if (e.key === 'Escape') { input.value = original; input.blur(); }
  });
}

async function deleteChatById(sessionId, isActive) {
  if (!confirm('Delete this chat?')) return;
  await fetch(`/api/chats/${sessionId}`, { method: 'DELETE' });
  if (isActive) newChat();
  else loadChatList();
}

async function loadChatList() {
  if (chatSearchEl && chatSearchEl.value.trim()) return; // don't overwrite search results
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
      chatListEl.appendChild(buildChatItem(chat));
      if (chat.id === SESSION_ID && chat.name) chatTitle.textContent = chat.name;
    }
  } catch {
    chatListEl.innerHTML = '<p class="text-gray-600 text-xs px-4 py-3">Failed to load chats</p>';
  }
}

// --- Chat search ---

let _searchTimeout = null;

chatSearchEl.addEventListener('input', (e) => {
  clearTimeout(_searchTimeout);
  const q = e.target.value.trim();
  if (!q) { loadChatList(); return; }
  _searchTimeout = setTimeout(() => runChatSearch(q), 300);
});

chatSearchEl.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { chatSearchEl.value = ''; loadChatList(); }
});

async function runChatSearch(query) {
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    chatListEl.innerHTML = '';
    if (!data.results || data.results.length === 0) {
      chatListEl.innerHTML = '<p class="text-gray-600 text-xs px-4 py-3">No results</p>';
      return;
    }
    for (const r of data.results) {
      const btn = document.createElement('button');
      btn.className = 'w-full text-left px-3 py-2.5 mx-1 rounded-lg text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors';

      const name = document.createElement('div');
      name.className = 'truncate text-sm font-medium';
      name.textContent = r.chat_name;

      const snippet = document.createElement('div');
      snippet.className = 'text-xs mt-0.5 text-gray-600 truncate';
      snippet.textContent = r.snippet;

      btn.appendChild(name);
      btn.appendChild(snippet);
      btn.addEventListener('click', () => {
        chatSearchEl.value = '';
        switchChat(r.session_id);
      });
      chatListEl.appendChild(btn);
    }
  } catch {}
}

// --- WebSocket ---

function connect() {
  const wsUrl = `ws://${location.host}/ws/chat?session_id=${SESSION_ID}`;
  socket = new WebSocket(wsUrl);

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
      if (currentBubble && currentBubble.dataset.searching) {
        // First token after search — restore streaming state
        currentBubble.classList.add('streaming');
        delete currentBubble.dataset.searching;
      }
      appendToken(data.content);
    } else if (data.type === 'searching') {
      if (!currentBubble) startAssistantBubble();
      currentBubble.dataset.searching = '1';
      currentBubble.classList.remove('streaming');
      currentBubble.innerHTML = '';
      const span = document.createElement('span');
      span.className = 'italic text-gray-500 text-xs';
      span.textContent = `Searching the web for "${data.query}"…`;
      currentBubble.appendChild(span);
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

function formatTimestamp(tsInput) {
  const d = tsInput instanceof Date ? tsInput
    : new Date(typeof tsInput === 'string' && !tsInput.endsWith('Z') ? tsInput + 'Z' : tsInput);
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

function appendMessage(role, content = '', timestamp = null) {
  showMessages();
  const wrapper = document.createElement('div');
  wrapper.className = `flex flex-col ${role === 'user' ? 'items-end' : 'items-start'}`;

  const bubble = document.createElement('div');
  bubble.className = role === 'user'
    ? 'max-w-xl bg-indigo-600 text-white px-4 py-3 rounded-2xl rounded-tr-sm text-sm'
    : 'max-w-xl bg-gray-800 text-gray-100 px-4 py-3 rounded-2xl rounded-tl-sm text-sm message-content';

  if (role === 'assistant' && content) {
    bubble.innerHTML = marked.parse(content);
  } else {
    bubble.textContent = content;
  }

  wrapper.appendChild(bubble);

  if (timestamp) {
    const ts = document.createElement('div');
    ts.className = `text-xs mt-1 text-gray-600 ${role === 'user' ? 'pr-1' : 'pl-1'}`;
    ts.textContent = formatTimestamp(timestamp);
    wrapper.appendChild(ts);
  }

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
    if (currentText) {
      currentBubble.innerHTML = marked.parse(currentText);
    }
    // Add timestamp below the bubble
    const ts = document.createElement('div');
    ts.className = 'text-xs mt-1 text-gray-600 pl-1';
    ts.textContent = formatTimestamp(new Date());
    currentBubble.parentElement.appendChild(ts);
    currentBubble = null;
    currentText = '';
  }
  if (ttsEnabled) flushTTSBuffer();
  isStreaming = false;
  sendBtn.classList.remove('hidden');
  stopBtn.classList.add('hidden');
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

// --- Image handling ---

let currentImageData = null;

async function compressImage(file) {
  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const MAX = 1024;
      let w = img.width, h = img.height;
      if (w > MAX || h > MAX) {
        if (w > h) { h = Math.round(h * MAX / w); w = MAX; }
        else { w = Math.round(w * MAX / h); h = MAX; }
      }
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      canvas.getContext('2d').drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL('image/jpeg', 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
    img.src = url;
  });
}

function setAttachedImage(dataUrl) {
  currentImageData = dataUrl;
  imagePreviewEl.src = dataUrl;
  imagePreviewArea.classList.remove('hidden');
}

function clearAttachedImage() {
  currentImageData = null;
  imagePreviewEl.src = '';
  imagePreviewArea.classList.add('hidden');
  imageInput.value = '';
}

function loadImageFile(file) {
  if (!file || !file.type.startsWith('image/')) return;
  compressImage(file).then(dataUrl => { if (dataUrl) setAttachedImage(dataUrl); });
}

imageBtn.addEventListener('click', () => imageInput.click());
imageInput.addEventListener('change', (e) => { if (e.target.files[0]) loadImageFile(e.target.files[0]); });
imageRemoveBtn.addEventListener('click', clearAttachedImage);

// Paste to attach image
document.addEventListener('paste', (e) => {
  if (isStreaming) return;
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault();
      loadImageFile(item.getAsFile());
      break;
    }
  }
});

function appendImageMessage(dataUrl) {
  showMessages();
  const wrapper = document.createElement('div');
  wrapper.className = 'flex justify-end';
  const img = document.createElement('img');
  img.src = dataUrl;
  img.className = 'max-w-xs max-h-48 rounded-xl border border-gray-700 object-cover';
  img.alt = 'Attached image';
  wrapper.appendChild(img);
  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function sendMessage() {
  const content = inputEl.value.trim();
  if (!content && !currentImageData) return;
  if (isStreaming || !socket || socket.readyState !== WebSocket.OPEN) return;

  if (currentImageData) appendImageMessage(currentImageData);
  if (content) appendMessage('user', content, new Date());

  inputEl.value = '';
  const imageToSend = currentImageData;
  clearAttachedImage();
  isStreaming = true;
  sendBtn.classList.add('hidden');
  stopBtn.classList.remove('hidden');
  resetTTS();
  setInputEnabled(false);
  startAssistantBubble();

  socket.send(JSON.stringify({
    type: 'message',
    content,
    provider: providerSelect.value,
    ...(imageToSend && { image: imageToSend }),
  }));
}

sendBtn.addEventListener('click', sendMessage);
stopBtn.addEventListener('click', () => {
  // Close WebSocket to cancel the backend stream, then reconnect
  if (socket) {
    socket.onclose = null;
    socket.close();
    socket = null;
  }
  finishStreaming();
  connect();
});
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

// --- Briefing badge ---

const briefingBadge = document.getElementById('briefing-badge');
let _briefingBadgePoll = null;

function checkBriefingBadge() {
  fetch('/api/briefing/status')
    .then(r => r.json())
    .then(data => {
      if (data.status === 'generating') {
        briefingBadge.classList.remove('hidden');
        if (!_briefingBadgePoll) {
          _briefingBadgePoll = setInterval(checkBriefingBadge, 3000);
        }
      } else {
        briefingBadge.classList.add('hidden');
        if (_briefingBadgePoll) {
          clearInterval(_briefingBadgePoll);
          _briefingBadgePoll = null;
        }
      }
    })
    .catch(() => {});
}

// --- Export ---

exportBtn.addEventListener('click', async () => {
  try {
    const res = await fetch(`/api/history/${SESSION_ID}`);
    const data = await res.json();
    const messages = data.messages || [];
    if (messages.length === 0) return;

    const title = chatTitle.textContent || 'Chat';
    const lines = [`# ${title}\n`];
    for (const msg of messages) {
      const label = msg.role === 'user' ? '**You**' : '**Assistant**';
      const time = msg.timestamp ? ` — ${formatTimestamp(msg.timestamp)}` : '';
      lines.push(`${label}${time}\n\n${msg.content}\n`);
    }
    const text = lines.join('\n---\n\n');
    const blob = new Blob([text], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  } catch {}
});

// --- Init ---

async function loadProviders() {
  try {
    const res = await fetch('/api/providers');
    const data = await res.json();
    const saved = localStorage.getItem('selected_provider');
    providerSelect.innerHTML = '';
    for (const p of data.providers) {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.label;
      if ((saved && p.id === saved) || (!saved && p.id === data.default)) opt.selected = true;
      providerSelect.appendChild(opt);
    }
  } catch {
    providerSelect.innerHTML = '<option value="ollama">Ollama</option>';
  }
  providerSelect.addEventListener('change', () => {
    localStorage.setItem('selected_provider', providerSelect.value);
  });
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
        appendMessage(msg.role, msg.content, msg.timestamp || null);
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
checkBriefingBadge();
