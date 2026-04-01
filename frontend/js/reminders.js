function formatDue(iso) {
  if (!iso) return null;
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  const now = new Date();
  const diff = d - now;
  const abs = Math.abs(diff);
  const mins = Math.floor(abs / 60000);
  const hours = Math.floor(abs / 3600000);
  const days = Math.floor(abs / 86400000);

  const past = diff < 0;
  let rel;
  if (mins < 1) rel = 'now';
  else if (mins < 60) rel = `${mins}m`;
  else if (hours < 24) rel = `${hours}h`;
  else if (days === 1) rel = 'tomorrow';
  else if (days < 7) rel = `${days}d`;
  else rel = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  return { label: `${past ? 'overdue' : 'in'} ${rel} · ${time}`, overdue: past };
}

async function loadReminders() {
  try {
    const res = await fetch('/api/reminders');
    const data = await res.json();
    const reminders = data.reminders || [];

    document.getElementById('reminders-loading').classList.add('hidden');
    renderReminders(reminders);
  } catch {
    document.getElementById('reminders-loading').classList.add('hidden');
    document.getElementById('reminders-empty').classList.remove('hidden');
  }
}

function renderReminders(reminders) {
  const list = document.getElementById('reminders-list');
  const empty = document.getElementById('reminders-empty');
  const count = document.getElementById('reminder-count');

  if (reminders.length === 0) {
    list.classList.add('hidden');
    empty.classList.remove('hidden');
    count.textContent = '';
    return;
  }

  empty.classList.add('hidden');
  list.classList.remove('hidden');
  count.textContent = `${reminders.length} pending`;
  list.innerHTML = '';

  for (const r of reminders) {
    const row = document.createElement('div');
    const due = r.due_time ? formatDue(r.due_time) : null;
    row.className = `group flex items-center gap-3 bg-gray-900 border rounded-xl px-4 py-3 transition-colors ${
      due?.overdue ? 'border-red-900/50 hover:border-red-800/50' : 'border-gray-800 hover:border-gray-700'
    }`;

    // Complete button
    const completeBtn = document.createElement('button');
    completeBtn.className = 'w-5 h-5 rounded-full border-2 border-gray-700 hover:border-indigo-500 flex-shrink-0 transition-colors flex items-center justify-center';
    completeBtn.title = 'Mark complete';
    completeBtn.addEventListener('click', () => doComplete(r.id, row));

    // Text + due
    const body = document.createElement('div');
    body.className = 'flex-1 min-w-0';

    const text = document.createElement('p');
    text.className = 'text-sm text-gray-200 truncate';
    text.textContent = r.text;
    body.appendChild(text);

    if (due) {
      const dueEl = document.createElement('p');
      dueEl.className = `text-xs mt-0.5 ${due.overdue ? 'text-red-400' : 'text-gray-600'}`;
      dueEl.textContent = due.label;
      body.appendChild(dueEl);
    }

    // Delete button
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'opacity-0 group-hover:opacity-100 p-1 text-gray-700 hover:text-red-400 rounded transition-all flex-shrink-0';
    deleteBtn.title = 'Delete';
    deleteBtn.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>`;
    deleteBtn.addEventListener('click', () => doDelete(r.id, row));

    row.appendChild(completeBtn);
    row.appendChild(body);
    row.appendChild(deleteBtn);
    list.appendChild(row);
  }
}

async function doComplete(id, row) {
  row.style.opacity = '0.4';
  row.style.pointerEvents = 'none';
  try {
    await fetch(`/api/reminders/${id}/complete`, { method: 'POST' });
    row.remove();
    updateCount(-1);
  } catch {
    row.style.opacity = '';
    row.style.pointerEvents = '';
  }
}

async function doDelete(id, row) {
  row.style.opacity = '0.4';
  row.style.pointerEvents = 'none';
  try {
    await fetch(`/api/reminders/${id}`, { method: 'DELETE' });
    row.remove();
    updateCount(-1);
  } catch {
    row.style.opacity = '';
    row.style.pointerEvents = '';
  }
}

function updateCount(delta) {
  const list = document.getElementById('reminders-list');
  const remaining = list.children.length;
  if (remaining === 0) {
    list.classList.add('hidden');
    document.getElementById('reminders-empty').classList.remove('hidden');
    document.getElementById('reminder-count').textContent = '';
  } else {
    document.getElementById('reminder-count').textContent = `${remaining} pending`;
  }
}

// --- Quick add ---

async function addReminder() {
  const textEl = document.getElementById('add-text');
  const dueEl = document.getElementById('add-due');
  const text = textEl.value.trim();
  if (!text) return;

  const addBtn = document.getElementById('add-btn');
  addBtn.disabled = true;

  // Convert local datetime to UTC ISO
  let due_time = null;
  if (dueEl.value) {
    due_time = new Date(dueEl.value).toISOString();
  }

  try {
    await fetch('/api/reminders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, due_time }),
    });
    textEl.value = '';
    dueEl.value = '';
    loadReminders();
  } catch {
    // non-fatal
  } finally {
    addBtn.disabled = false;
  }
}

document.getElementById('add-btn').addEventListener('click', addReminder);
document.getElementById('add-text').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') addReminder();
});

loadReminders();
