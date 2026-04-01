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

const chatListEl = document.getElementById('chat-list');
const chatSearchEl = document.getElementById('chat-search');

function buildHomeChatItem(chat) {
  const item = document.createElement('div');
  item.className = 'group relative flex items-center mx-1 rounded-lg hover:bg-gray-800';

  const btn = document.createElement('button');
  btn.className = 'flex-1 text-left px-3 py-2.5 rounded-lg transition-colors min-w-0 text-gray-400 hover:text-gray-200';

  const nameEl = document.createElement('div');
  nameEl.className = 'truncate text-sm font-medium';
  nameEl.textContent = chat.name || 'New chat';

  const timeEl = document.createElement('div');
  timeEl.className = 'text-xs mt-0.5 opacity-50 truncate';
  timeEl.textContent = formatRelativeTime(chat.last_active);

  btn.appendChild(nameEl);
  btn.appendChild(timeEl);
  btn.addEventListener('click', () => {
    localStorage.setItem('active_session_id', chat.id);
    window.location.href = '/chat';
  });

  const actions = document.createElement('div');
  actions.className = 'flex items-center gap-0.5 pr-1.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0';

  const renameBtn = document.createElement('button');
  renameBtn.className = 'p-1 text-gray-600 hover:text-gray-400 rounded transition-colors';
  renameBtn.title = 'Rename';
  renameBtn.innerHTML = `<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>`;
  renameBtn.addEventListener('click', (e) => { e.stopPropagation(); startHomeRename(chat, nameEl); });

  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'p-1 text-gray-600 hover:text-red-400 rounded transition-colors';
  deleteBtn.title = 'Delete';
  deleteBtn.innerHTML = `<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>`;
  deleteBtn.addEventListener('click', (e) => { e.stopPropagation(); deleteHomeChat(chat.id); });

  actions.appendChild(renameBtn);
  actions.appendChild(deleteBtn);
  item.appendChild(btn);
  item.appendChild(actions);
  return item;
}

async function startHomeRename(chat, nameEl) {
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
    const newEl = document.createElement('div');
    newEl.className = 'truncate text-sm font-medium';
    newEl.textContent = name || original;
    input.replaceWith(newEl);
    if (name && name !== original) {
      await fetch(`/api/chats/${chat.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      loadChatList();
    }
  }

  input.addEventListener('blur', save);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    if (e.key === 'Escape') { input.value = original; input.blur(); }
  });
}

async function deleteHomeChat(sessionId) {
  if (!confirm('Delete this chat?')) return;
  await fetch(`/api/chats/${sessionId}`, { method: 'DELETE' });
  loadChatList();
}

async function loadChatList() {
  if (chatSearchEl && chatSearchEl.value.trim()) return;
  try {
    const res = await fetch('/api/chats');
    const data = await res.json();
    const chats = data.chats || [];
    chatListEl.innerHTML = '';
    if (chats.length === 0) {
      chatListEl.innerHTML = '<p class="text-gray-600 text-xs px-4 py-3">No previous chats</p>';
      return;
    }
    for (const chat of chats) chatListEl.appendChild(buildHomeChatItem(chat));
  } catch {
    chatListEl.innerHTML = '<p class="text-gray-600 text-xs px-4 py-3">Failed to load chats</p>';
  }
}

// --- Chat search (home) ---

let _homeSearchTimeout = null;

chatSearchEl.addEventListener('input', (e) => {
  clearTimeout(_homeSearchTimeout);
  const q = e.target.value.trim();
  if (!q) { loadChatList(); return; }
  _homeSearchTimeout = setTimeout(() => runHomeSearch(q), 300);
});

chatSearchEl.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { chatSearchEl.value = ''; loadChatList(); }
});

async function runHomeSearch(query) {
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
        localStorage.setItem('active_session_id', r.session_id);
        window.location.href = '/chat';
      });
      chatListEl.appendChild(btn);
    }
  } catch {}
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
  tile.id = 'calendar-tile';
  tile.className = 'bg-gray-900 border border-gray-800 rounded-2xl p-5';

  const header = document.createElement('div');
  header.className = 'text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3';
  header.textContent = "Calendar";
  tile.appendChild(header);

  if (events.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'flex flex-col items-center justify-center py-3 text-center gap-1';

    const graphic = document.createElement('div');
    graphic.className = 'text-2xl mb-1';
    graphic.textContent = '✨';

    const msg = document.createElement('p');
    msg.className = 'text-sm text-gray-300 font-medium';
    msg.textContent = 'All clear!';

    const sub = document.createElement('p');
    sub.className = 'text-xs text-gray-600';
    const hour = new Date().getHours();
    sub.textContent = hour >= 18
      ? 'Nothing left today or tomorrow morning'
      : 'Nothing left on your schedule today';

    empty.appendChild(graphic);
    empty.appendChild(msg);
    empty.appendChild(sub);
    tile.appendChild(empty);
    return tile;
  }

  const list = document.createElement('div');
  list.className = 'space-y-2';

  let lastWasTomorrow = false;
  for (const event of events) {
    // Insert a subtle divider before the first tomorrow event
    if (event.status === 'tomorrow' && !lastWasTomorrow) {
      const divider = document.createElement('div');
      divider.className = 'flex items-center gap-2 pt-1';
      const line = document.createElement('div');
      line.className = 'flex-1 h-px bg-gray-800';
      const label = document.createElement('span');
      label.className = 'text-xs text-gray-700 flex-shrink-0';
      label.textContent = 'Tomorrow';
      divider.appendChild(line);
      divider.appendChild(label);
      list.appendChild(divider);
      lastWasTomorrow = true;
    }

    const row = document.createElement('div');

    const status = event.status || 'upcoming';

    if (status === 'current') {
      row.className = 'flex items-center gap-3 px-2 py-1 -mx-2 bg-indigo-600/10 rounded-lg border border-indigo-600/20';
    } else {
      row.className = 'flex items-baseline gap-3';
    }

    const timeEl = document.createElement('span');
    timeEl.className = 'text-xs font-medium flex-shrink-0 w-16 ' + ({
      past:     'text-gray-600',
      current:  'text-indigo-400',
      upcoming: 'text-indigo-400',
      tomorrow: 'text-gray-500',
    }[status] || 'text-indigo-400');
    timeEl.textContent = event.start;

    const titleEl = document.createElement('span');
    titleEl.className = 'text-sm truncate ' + ({
      past:     'text-gray-600 line-through',
      current:  'text-indigo-200 font-medium',
      upcoming: 'text-gray-200',
      tomorrow: 'text-gray-400',
    }[status] || 'text-gray-200');
    titleEl.textContent = event.title;

    row.appendChild(timeEl);
    row.appendChild(titleEl);

    if (status === 'current') {
      const badge = document.createElement('span');
      badge.className = 'text-xs text-indigo-400 font-medium ml-auto flex-shrink-0';
      badge.textContent = 'Now';
      row.appendChild(badge);
    }

    list.appendChild(row);
  }

  tile.appendChild(list);
  return tile;
}

// --- Tasks tile (Todoist) ---

function buildTasksTile(tasks) {
  const tile = document.createElement('div');
  tile.id = 'tasks-tile';
  tile.className = 'bg-gray-900 border border-gray-800 rounded-2xl p-5';

  const header = document.createElement('div');
  header.className = 'flex items-center justify-between mb-3';

  const label = document.createElement('div');
  label.className = 'text-xs font-semibold text-gray-500 uppercase tracking-wider';
  label.textContent = 'Tasks';

  const refreshBtn = document.createElement('button');
  refreshBtn.className = 'text-gray-600 hover:text-gray-400 transition-colors p-0.5 rounded';
  refreshBtn.title = 'Refresh tasks';
  refreshBtn.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>`;
  refreshBtn.addEventListener('click', loadTasksTile);

  header.appendChild(label);
  header.appendChild(refreshBtn);
  tile.appendChild(header);

  if (tasks.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'text-sm text-gray-600 py-1';
    empty.textContent = 'No tasks due today';
    tile.appendChild(empty);
    return tile;
  }

  const list = document.createElement('div');
  list.className = 'space-y-2';

  for (const task of tasks) {
    const row = document.createElement('div');
    row.className = 'flex items-start gap-2.5';

    const dot = document.createElement('span');
    dot.className = 'text-indigo-500 text-xs mt-1 flex-shrink-0';
    dot.textContent = '●';

    const text = document.createElement('span');
    text.className = 'text-sm text-gray-200 leading-snug';
    text.textContent = task.content;

    row.appendChild(dot);
    row.appendChild(text);

    if (task.due) {
      const due = document.createElement('span');
      due.className = 'text-xs text-gray-600 ml-auto flex-shrink-0 mt-0.5';
      due.textContent = task.due.string || '';
      row.appendChild(due);
    }

    list.appendChild(row);
  }

  tile.appendChild(list);
  return tile;
}

async function loadTasksTile() {
  try {
    const res = await fetch('/api/todoist/tasks');
    if (!res.ok) return;
    const data = await res.json();
    if (!data.enabled) return;

    const tilesEl = document.getElementById('briefing-tiles');
    if (!tilesEl || tilesEl.classList.contains('hidden')) return;

    const existing = document.getElementById('tasks-tile');
    const newTile = buildTasksTile(data.tasks);

    if (existing) {
      existing.parentNode.replaceChild(newTile, existing);
    } else {
      // Insert before reminders tile if present, otherwise append
      const reminders = tilesEl.querySelector('.reminders-tile');
      if (reminders) {
        tilesEl.insertBefore(newTile, reminders);
      } else {
        tilesEl.appendChild(newTile);
      }
    }
  } catch {
    // Non-fatal
  }
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

  // Top row: weather + calendar always side by side
  const hasCalendar = data.events !== undefined;
  if (hasWeather && hasCalendar) {
    const row = document.createElement('div');
    row.className = 'grid grid-cols-1 sm:grid-cols-2 gap-3';
    row.appendChild(buildWeatherTile(data.weather));
    row.appendChild(buildCalendarTile(data.events));
    container.appendChild(row);
  } else if (hasWeather) {
    container.appendChild(buildWeatherTile(data.weather));
  } else if (hasCalendar) {
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

let _briefingPollInterval = null;

function stopBriefingPoll() {
  if (_briefingPollInterval) { clearInterval(_briefingPollInterval); _briefingPollInterval = null; }
}

function onBriefingReady(data) {
  stopBriefingPoll();
  document.getElementById('refresh-icon').classList.remove('spin');
  renderBriefing(data);
  refreshCalendarTile();
  loadTasksTile();
  loadEmailTile();
}

async function loadBriefing(force = false) {
  const period = getPeriod();
  document.getElementById('briefing-label').textContent = PERIOD_LABELS[period];

  document.getElementById('briefing-tiles').classList.add('hidden');
  document.getElementById('briefing-error').classList.add('hidden');
  document.getElementById('briefing-loading').classList.remove('hidden');

  const icon = document.getElementById('refresh-icon');
  icon.classList.add('spin');
  stopBriefingPoll();

  let data;
  try {
    const provider = document.getElementById('provider-select').value;
    const res = await fetch('/api/briefing/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ period, force, provider }),
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

  // Background generation — poll until ready
  if (data.status === 'generating') {
    _briefingPollInterval = setInterval(async () => {
      try {
        const res = await fetch('/api/briefing/status');
        const poll = await res.json();
        if (poll.status === 'error') {
          stopBriefingPoll();
          icon.classList.remove('spin');
          document.getElementById('briefing-loading').classList.add('hidden');
          document.getElementById('briefing-error').classList.remove('hidden');
        } else if (poll.status !== 'generating') {
          onBriefingReady(poll);
        }
      } catch {}
    }, 2000);
    return;
  }

  onBriefingReady(data);
}

document.getElementById('briefing-refresh').addEventListener('click', () => loadBriefing(true));

// --- Providers ---

async function loadProviders() {
  const select = document.getElementById('provider-select');
  try {
    const res = await fetch('/api/providers');
    const data = await res.json();
    const saved = localStorage.getItem('selected_provider');
    select.innerHTML = '';
    for (const p of data.providers) {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.label;
      if ((saved && p.id === saved) || (!saved && p.id === data.default)) opt.selected = true;
      select.appendChild(opt);
    }
  } catch {
    select.innerHTML = '<option value="ollama">Ollama</option>';
  }
  select.addEventListener('change', () => {
    localStorage.setItem('selected_provider', select.value);
  });
}

// --- Calendar live refresh ---

async function refreshCalendarTile() {
  try {
    const res = await fetch('/api/calendar/events');
    if (!res.ok) return;
    const data = await res.json();
    const existing = document.getElementById('calendar-tile');
    if (!existing) return;
    const newTile = buildCalendarTile(data.events);
    existing.parentNode.replaceChild(newTile, existing);
  } catch {
    // Non-fatal — skip this refresh cycle
  }
}

const CALENDAR_REFRESH_MS = 5 * 60 * 1000; // 5 minutes
setInterval(refreshCalendarTile, CALENDAR_REFRESH_MS);

// --- Email tile ---

function buildEmailTile(data) {
  const tile = document.createElement('div');
  tile.id = 'email-tile';
  tile.className = 'bg-gray-900 border border-gray-800 rounded-2xl p-5';

  const header = document.createElement('div');
  header.className = 'flex items-center justify-between mb-3';

  const label = document.createElement('div');
  label.className = 'text-xs font-semibold text-gray-500 uppercase tracking-wider';
  const countLabel = Object.entries(data.account_counts || {})
    .map(([acc, n]) => `${n} from ${acc}`)
    .join(' · ') || `${data.count} email${data.count !== 1 ? 's' : ''}`;
  label.textContent = `Email — ${countLabel}`;

  const refreshBtn = document.createElement('button');
  refreshBtn.className = 'text-gray-600 hover:text-gray-400 transition-colors p-0.5 rounded';
  refreshBtn.title = 'Refresh emails';
  refreshBtn.innerHTML = `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>`;
  refreshBtn.addEventListener('click', () => loadEmailTile(true));

  header.appendChild(label);
  header.appendChild(refreshBtn);
  tile.appendChild(header);

  if (data.summary) {
    const summary = document.createElement('p');
    summary.className = 'text-sm text-gray-300 leading-relaxed mb-3';
    summary.textContent = data.summary;
    tile.appendChild(summary);
  }

  if (data.emails && data.emails.length > 0) {
    const list = document.createElement('div');
    list.className = 'space-y-2 border-t border-gray-800 pt-3';
    for (const e of data.emails.slice(0, 6)) {
      const row = document.createElement('div');
      row.className = 'flex items-baseline gap-2 min-w-0';

      const from = document.createElement('span');
      from.className = 'text-xs font-medium text-indigo-400 flex-shrink-0 max-w-[120px] truncate';
      from.textContent = e.from;

      const subj = document.createElement('span');
      subj.className = 'text-sm text-gray-300 truncate';
      subj.textContent = e.subject;

      const time = document.createElement('span');
      time.className = 'text-xs text-gray-600 flex-shrink-0 ml-auto';
      time.textContent = e.date || '';

      row.appendChild(from);
      row.appendChild(subj);
      if (e.date) row.appendChild(time);
      list.appendChild(row);
    }
    tile.appendChild(list);
  }

  return tile;
}

async function loadEmailTile(force = false) {
  try {
    const provider = document.getElementById('provider-select')?.value || '';
    const res = await fetch(`/api/email/summary?force=${force}&provider=${encodeURIComponent(provider)}`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.enabled || data.count === 0) return;

    const tilesEl = document.getElementById('briefing-tiles');
    if (!tilesEl || tilesEl.classList.contains('hidden')) return;

    const existing = document.getElementById('email-tile');
    const newTile = buildEmailTile(data);
    if (existing) {
      existing.parentNode.replaceChild(newTile, existing);
    } else {
      tilesEl.appendChild(newTile);
    }
  } catch {
    // Non-fatal
  }
}

// --- Init ---

setGreeting();
loadProviders().then(() => loadBriefing());
loadChatList();
