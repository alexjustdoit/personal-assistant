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
    text.className = 'flex-1 text-sm text-gray-200 leading-relaxed cursor-pointer hover:text-white transition-colors';
    text.title = 'Click to edit';
    text.textContent = mem.text;
    text.addEventListener('click', () => startEditMemory(mem, text, row));

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

function startEditMemory(mem, textEl, row) {
  const textarea = document.createElement('textarea');
  textarea.className = 'flex-1 text-sm bg-gray-800 text-gray-100 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 leading-relaxed';
  textarea.value = mem.text;
  textarea.rows = Math.max(2, Math.ceil(mem.text.length / 60));

  const btnRow = document.createElement('div');
  btnRow.className = 'flex gap-2 mt-2';
  const saveBtn = document.createElement('button');
  saveBtn.className = 'text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded-lg transition-colors';
  saveBtn.textContent = 'Save';
  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'text-xs text-gray-500 hover:text-gray-300 px-3 py-1 rounded-lg transition-colors';
  cancelBtn.textContent = 'Cancel';

  cancelBtn.addEventListener('click', () => { textarea.replaceWith(textEl); btnRow.remove(); });
  saveBtn.addEventListener('click', async () => {
    const newText = textarea.value.trim();
    if (!newText || newText === mem.text) { textarea.replaceWith(textEl); btnRow.remove(); return; }
    saveBtn.disabled = true;
    try {
      await fetch(`/api/memories/${encodeURIComponent(mem.id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: newText }),
      });
      mem.text = newText;
      textEl.textContent = newText;
      const idx = _allMemories.findIndex(m => m.id === mem.id);
      if (idx !== -1) _allMemories[idx].text = newText;
      textarea.replaceWith(textEl);
      btnRow.remove();
    } catch {
      saveBtn.disabled = false;
    }
  });
  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { textarea.replaceWith(textEl); btnRow.remove(); }
  });

  btnRow.appendChild(cancelBtn);
  btnRow.appendChild(saveBtn);
  textEl.replaceWith(textarea);
  row.appendChild(btnRow);
  textarea.focus();
  textarea.select();
}

loadMemories();
