// --- Sidebar ---

const sidebar = document.getElementById('sidebar');
const sidebarBackdrop = document.getElementById('sidebar-backdrop');
const sidebarToggle = document.getElementById('sidebar-toggle');
const newChatBtn = document.getElementById('new-chat-btn');

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
newChatBtn.addEventListener('click', () => {
  localStorage.setItem('active_session_id', crypto.randomUUID());
  window.location.href = '/chat';
});

setSidebar(sidebarOpen);

// --- Chat list (sidebar) ---

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
  const chatListEl = document.getElementById('chat-list');
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
      const btn = document.createElement('button');
      btn.className = 'chat-list-item w-full text-left px-3 py-2.5 mx-1 rounded-lg transition-colors text-gray-400 hover:bg-gray-800 hover:text-gray-200';

      const name = document.createElement('div');
      name.className = 'truncate text-sm font-medium';
      name.textContent = chat.name || 'New chat';

      const time = document.createElement('div');
      time.className = 'text-xs mt-0.5 opacity-50 truncate';
      time.textContent = formatRelativeTime(chat.last_active);

      btn.appendChild(name);
      btn.appendChild(time);
      btn.addEventListener('click', () => {
        localStorage.setItem('active_session_id', chat.id);
        window.location.href = '/chat';
      });

      chatListEl.appendChild(btn);
    }
  } catch {
    chatListEl.innerHTML = '<p class="text-gray-600 text-xs px-4 py-3">Failed to load chats</p>';
  }
}

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

// --- Weather tile ---

function weatherEmoji(description) {
  const d = description.toLowerCase();
  if (d.includes('thunderstorm')) return '⛈️';
  if (d.includes('drizzle') || d.includes('shower')) return '🌦️';
  if (d.includes('rain')) return '🌧️';
  if (d.includes('snow')) return '❄️';
  if (d.includes('sleet') || d.includes('ice')) return '🌨️';
  if (d.includes('fog') || d.includes('mist') || d.includes('haze')) return '🌫️';
  if (d.includes('overcast')) return '☁️';
  if (d.includes('broken clouds') || d.includes('scattered')) return '⛅';
  if (d.includes('few clouds') || d.includes('partly')) return '🌤️';
  if (d.includes('clear')) return '☀️';
  return '🌡️';
}

function buildWeatherTile(weather) {
  const tile = document.createElement('div');
  tile.className = 'bg-gray-900 border border-gray-800 rounded-2xl p-5 flex items-center gap-5';

  const icon = document.createElement('div');
  icon.className = 'text-5xl flex-shrink-0';
  icon.textContent = weatherEmoji(weather.description);

  const info = document.createElement('div');
  info.className = 'min-w-0';

  const temp = document.createElement('div');
  temp.className = 'text-3xl font-semibold text-gray-100';
  temp.textContent = `${weather.temp}${weather.unit}`;

  const desc = document.createElement('div');
  desc.className = 'text-gray-300 text-sm mt-0.5';
  desc.textContent = weather.description;

  const meta = document.createElement('div');
  meta.className = 'text-gray-600 text-xs mt-1';
  meta.textContent = `Feels like ${weather.feels_like}${weather.unit} · ${weather.humidity}% humidity · ${weather.city}`;

  info.appendChild(temp);
  info.appendChild(desc);
  info.appendChild(meta);
  tile.appendChild(icon);
  tile.appendChild(info);
  return tile;
}

// --- Calendar tile ---

function buildCalendarTile(events) {
  const tile = document.createElement('div');
  tile.className = 'bg-gray-900 border border-gray-800 rounded-2xl p-5';

  const header = document.createElement('div');
  header.className = 'text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3';
  header.textContent = "Today's Calendar";
  tile.appendChild(header);

  if (events.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'text-gray-600 text-sm';
    empty.textContent = 'No events today';
    tile.appendChild(empty);
    return tile;
  }

  const list = document.createElement('div');
  list.className = 'space-y-2';
  for (const event of events) {
    const row = document.createElement('div');
    row.className = 'flex items-baseline gap-3';

    const time = document.createElement('span');
    time.className = 'text-xs text-indigo-400 font-medium flex-shrink-0 w-16';
    time.textContent = event.start;

    const title = document.createElement('span');
    title.className = 'text-sm text-gray-200 truncate';
    title.textContent = event.title;

    row.appendChild(time);
    row.appendChild(title);
    list.appendChild(row);
  }
  tile.appendChild(list);
  return tile;
}

// --- Reminders tile ---

function buildRemindersTile(reminders) {
  const tile = document.createElement('div');
  tile.className = 'bg-gray-900 border border-gray-800 rounded-2xl p-5';

  const header = document.createElement('div');
  header.className = 'text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3';
  header.textContent = 'Reminders';
  tile.appendChild(header);

  const list = document.createElement('div');
  list.className = 'space-y-2';
  for (const r of reminders) {
    const row = document.createElement('div');
    row.className = 'flex items-baseline gap-2';

    const dot = document.createElement('span');
    dot.className = 'text-indigo-500 text-xs flex-shrink-0';
    dot.textContent = '●';

    const text = document.createElement('span');
    text.className = 'text-sm text-gray-200';
    text.textContent = r.text;

    if (r.due_time) {
      const due = document.createElement('span');
      due.className = 'text-xs text-gray-600 ml-auto flex-shrink-0';
      due.textContent = new Date(r.due_time + 'Z').toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
      row.appendChild(dot);
      row.appendChild(text);
      row.appendChild(due);
    } else {
      row.appendChild(dot);
      row.appendChild(text);
    }
    list.appendChild(row);
  }
  tile.appendChild(list);
  return tile;
}

// --- News cards ---

function buildNewsSection(tiles) {
  const wrapper = document.createElement('div');

  const header = document.createElement('div');
  header.className = 'text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3';
  header.textContent = 'News';
  wrapper.appendChild(header);

  const grid = document.createElement('div');
  grid.className = 'space-y-2';

  for (const tile of tiles) {
    const card = document.createElement('div');
    card.className = 'flex flex-col gap-1.5 px-4 py-3 bg-gray-900 border border-gray-800 rounded-xl';

    const topRow = document.createElement('div');
    topRow.className = 'flex items-center justify-between gap-2';

    const topic = document.createElement('span');
    topic.className = 'text-xs text-indigo-400 font-semibold uppercase tracking-wide';
    topic.textContent = tile.topic;

    topRow.appendChild(topic);
    card.appendChild(topRow);

    if (tile.summary) {
      const summary = document.createElement('div');
      summary.className = 'text-sm text-gray-300 leading-relaxed';
      summary.textContent = tile.summary;
      card.appendChild(summary);
    }

    if (tile.sources && tile.sources.length > 0) {
      const sources = document.createElement('div');
      sources.className = 'text-xs text-gray-600 mt-0.5';
      sources.textContent = 'Sources: ' + tile.sources.join(', ');
      card.appendChild(sources);
    }

    grid.appendChild(card);
  }

  wrapper.appendChild(grid);
  return wrapper;
}

// --- Render briefing tiles ---

function renderBriefing(data) {
  const container = document.getElementById('briefing-tiles');
  container.innerHTML = '';

  const hasWeather = data.weather;
  const hasNews = data.news && data.news.length > 0;
  const hasReminders = data.reminders && data.reminders.length > 0;

  const hasAnything = hasWeather || data.events !== undefined || hasNews || hasReminders;
  if (!hasAnything) {
    document.getElementById('briefing-loading').classList.add('hidden');
    document.getElementById('briefing-error').classList.remove('hidden');
    return;
  }

  // Ollama summary sentence
  if (data.summary) {
    const summaryCard = document.createElement('div');
    summaryCard.className = 'px-5 py-4 bg-indigo-950/40 border border-indigo-800/40 rounded-2xl';
    const summaryText = document.createElement('p');
    summaryText.className = 'text-gray-200 text-sm leading-relaxed italic';
    summaryText.textContent = data.summary;
    summaryCard.appendChild(summaryText);
    container.appendChild(summaryCard);
  }

  // Top row: weather + calendar side by side
  if (hasWeather && data.events !== undefined) {
    const row = document.createElement('div');
    row.className = 'grid grid-cols-1 sm:grid-cols-2 gap-3';
    row.appendChild(buildWeatherTile(data.weather));
    row.appendChild(buildCalendarTile(data.events));
    container.appendChild(row);
  } else if (hasWeather) {
    container.appendChild(buildWeatherTile(data.weather));
  } else if (data.events !== undefined) {
    container.appendChild(buildCalendarTile(data.events));
  }

  if (hasNews) container.appendChild(buildNewsSection(data.news));
  if (hasReminders) container.appendChild(buildRemindersTile(data.reminders));

  // Timestamp
  if (data.generated_at) {
    const ts = document.createElement('p');
    ts.className = 'text-gray-700 text-xs mt-1';
    const d = new Date(data.generated_at + (data.generated_at.endsWith('Z') ? '' : 'Z'));
    ts.textContent = 'Updated ' + d.toLocaleString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit',
    });
    container.appendChild(ts);
  }

  document.getElementById('briefing-loading').classList.add('hidden');
  container.classList.remove('hidden');
}

// --- Load briefing ---

async function loadBriefing(force = false) {
  const period = getPeriod();
  document.getElementById('briefing-label').textContent = PERIOD_LABELS[period];

  document.getElementById('briefing-tiles').classList.add('hidden');
  document.getElementById('briefing-error').classList.add('hidden');
  document.getElementById('briefing-loading').classList.remove('hidden');

  const icon = document.getElementById('refresh-icon');
  icon.classList.add('spin');

  let data;
  try {
    const res = await fetch('/api/briefing/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ period, force }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (err) {
    console.error('[briefing] fetch failed:', err);
    document.getElementById('briefing-loading').classList.add('hidden');
    document.getElementById('briefing-error').classList.remove('hidden');
    icon.classList.remove('spin');
    return;
  }

  icon.classList.remove('spin');
  renderBriefing(data);
}

document.getElementById('briefing-refresh').addEventListener('click', () => loadBriefing(true));

// --- Init ---

setGreeting();
loadBriefing();
loadChatList();
