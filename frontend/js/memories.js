let _allMemories = [];

document.getElementById('memory-search').addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase();
  renderMemories(q ? _allMemories.filter(m => m.text.toLowerCase().includes(q)) : _allMemories);
});

function renderMemories(memories) {
  const list = document.getElementById('memories-list');
  list.innerHTML = '';

  if (memories.length === 0) {
    list.innerHTML = '<p class="text-gray-600 text-sm py-4 text-center">No matching memories.</p>';
    list.classList.remove('hidden');
    return;
  }

  for (const mem of memories) {
    const row = document.createElement('div');
    row.className = 'group flex items-start gap-3 bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 hover:border-gray-700 transition-colors';

    const text = document.createElement('p');
    text.className = 'flex-1 text-sm text-gray-200 leading-relaxed';
    text.textContent = mem.text;

    const meta = document.createElement('div');
    meta.className = 'flex flex-col items-end gap-1.5 flex-shrink-0';

    if (mem.timestamp) {
      const ts = document.createElement('span');
      ts.className = 'text-xs text-gray-700';
      const d = new Date(mem.timestamp.endsWith('Z') ? mem.timestamp : mem.timestamp + 'Z');
      ts.textContent = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      meta.appendChild(ts);
    }

    const del = document.createElement('button');
    del.className = 'opacity-0 group-hover:opacity-100 text-gray-700 hover:text-red-400 transition-all p-0.5 rounded';
    del.title = 'Delete memory';
    del.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>`;
    del.addEventListener('click', () => deleteMemory(mem.id, row, mem));
    meta.appendChild(del);

    row.appendChild(text);
    row.appendChild(meta);
    list.appendChild(row);
  }
}

async function loadMemories() {
  try {
    const res = await fetch('/api/memories');
    const data = await res.json();
    _allMemories = data.memories || [];

    document.getElementById('memories-loading').classList.add('hidden');

    if (_allMemories.length === 0) {
      document.getElementById('memories-empty').classList.remove('hidden');
      return;
    }

    document.getElementById('memory-count').textContent = `${_allMemories.length} fact${_allMemories.length !== 1 ? 's' : ''}`;
    document.getElementById('memories-list').classList.remove('hidden');
    renderMemories(_allMemories);
  } catch {
    document.getElementById('memories-loading').classList.add('hidden');
    document.getElementById('memories-empty').classList.remove('hidden');
  }
}

async function deleteMemory(id, row, mem) {
  row.style.opacity = '0.4';
  row.style.pointerEvents = 'none';
  try {
    await fetch(`/api/memories/${encodeURIComponent(id)}`, { method: 'DELETE' });
    _allMemories = _allMemories.filter(m => m.id !== id);
    document.getElementById('memory-count').textContent = _allMemories.length
      ? `${_allMemories.length} fact${_allMemories.length !== 1 ? 's' : ''}`
      : '';
    const q = document.getElementById('memory-search').value.toLowerCase();
    const visible = q ? _allMemories.filter(m => m.text.toLowerCase().includes(q)) : _allMemories;
    if (_allMemories.length === 0) {
      document.getElementById('memories-list').classList.add('hidden');
      document.getElementById('memories-empty').classList.remove('hidden');
    } else {
      renderMemories(visible);
    }
  } catch {
    row.style.opacity = '';
    row.style.pointerEvents = '';
  }
}

loadMemories();
