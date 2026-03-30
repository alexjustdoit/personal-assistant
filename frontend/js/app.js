const messagesEl = document.getElementById('messages');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send-btn');
const statusDot = document.getElementById('status-dot');

const WS_URL = `ws://${location.host}/ws/chat`;
let socket = null;
let isStreaming = false;

function connect() {
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    statusDot.classList.replace('bg-red-500', 'bg-green-500');
    statusDot.classList.add('bg-green-500');
  };

  socket.onclose = () => {
    statusDot.classList.replace('bg-green-500', 'bg-red-500');
    setTimeout(connect, 3000); // reconnect
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

function appendMessage(role, content = '') {
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
    currentBubble = null;
    currentText = '';
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

  socket.send(JSON.stringify({ type: 'message', content }));
}

sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

connect();
