// --- Time period ---

function getPeriod() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 17) return 'afternoon';
  if (hour >= 17 && hour < 22) return 'evening';
  return 'night';
}

const PERIOD_LABELS = {
  morning: 'Morning Briefing',
  afternoon: 'Afternoon Check-in',
  evening: 'Evening Briefing',
  night: "Tonight's Overview",
};

// --- Greeting ---

function setGreeting() {
  const hour = new Date().getHours();
  let greeting;
  if (hour >= 5 && hour < 12) greeting = 'Good morning';
  else if (hour >= 12 && hour < 17) greeting = 'Good afternoon';
  else greeting = 'Good evening';
  document.getElementById('greeting').textContent = greeting;

  document.getElementById('date-line').textContent = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric',
  });
}

// --- Briefing ---

async function loadBriefing() {
  const period = getPeriod();
  document.getElementById('briefing-label').textContent = PERIOD_LABELS[period];

  try {
    const res = await fetch('/api/briefing/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ period }),
    });

    if (!res.ok) throw new Error('Request failed');
    const data = await res.json();

    document.getElementById('briefing-loading').classList.add('hidden');

    if (data.content) {
      document.getElementById('briefing-text').textContent = data.content;
      if (data.generated_at) {
        const d = new Date(data.generated_at + (data.generated_at.endsWith('Z') ? '' : 'Z'));
        document.getElementById('briefing-time').textContent =
          'Generated ' + d.toLocaleString('en-US', {
            weekday: 'short', month: 'short', day: 'numeric',
            hour: 'numeric', minute: '2-digit',
          });
      }
      document.getElementById('briefing-section').classList.remove('hidden');
    } else {
      document.getElementById('briefing-error').classList.remove('hidden');
    }
  } catch {
    document.getElementById('briefing-loading').classList.add('hidden');
    document.getElementById('briefing-error').classList.remove('hidden');
  }
}

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

async function loadChats() {
  const listEl = document.getElementById('chat-list');
  const noChatsEl = document.getElementById('no-chats');
  const loadingEl = document.getElementById('chats-loading');

  try {
    const res = await fetch('/api/chats');
    const data = await res.json();
    const chats = (data.chats || []).slice(0, 8);

    loadingEl.classList.add('hidden');

    if (chats.length === 0) {
      noChatsEl.classList.remove('hidden');
      return;
    }

    for (const chat of chats) {
      const item = document.createElement('a');
      item.href = '#';
      item.className = 'flex items-center justify-between px-4 py-3 bg-gray-900 border border-gray-800 rounded-xl hover:border-gray-700 hover:bg-gray-800/60 transition-all group cursor-pointer';
      item.addEventListener('click', (e) => {
        e.preventDefault();
        localStorage.setItem('active_session_id', chat.id);
        window.location.href = '/chat';
      });

      const left = document.createElement('div');
      left.className = 'min-w-0 flex-1';

      const name = document.createElement('div');
      name.className = 'text-sm text-gray-200 font-medium truncate group-hover:text-white transition-colors';
      name.textContent = chat.name || 'Untitled chat';

      const time = document.createElement('div');
      time.className = 'text-xs text-gray-600 mt-0.5';
      time.textContent = formatRelativeTime(chat.last_active);

      left.appendChild(name);
      left.appendChild(time);

      const arrow = document.createElement('span');
      arrow.className = 'text-gray-700 group-hover:text-gray-400 transition-colors ml-4 flex-shrink-0 text-sm';
      arrow.textContent = '→';

      item.appendChild(left);
      item.appendChild(arrow);
      listEl.appendChild(item);
    }
  } catch {
    loadingEl.classList.add('hidden');
    listEl.innerHTML = '<p class="text-gray-600 text-sm">Could not load recent chats.</p>';
  }
}

// --- New chat link ---

document.getElementById('new-chat-link').addEventListener('click', (e) => {
  e.preventDefault();
  localStorage.setItem('active_session_id', crypto.randomUUID());
  window.location.href = '/chat';
});

setGreeting();
loadBriefing();
loadChats();
