let _originalConfig = {};

// --- Load current config ---

async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    _originalConfig = await res.json();
    populate(_originalConfig);
  } catch {
    document.getElementById('save-status').textContent = 'Failed to load current settings.';
  }
}

function populate(cfg) {
  const llm = cfg.llm || {};
  const briefing = cfg.briefing || {};
  const weather = cfg.weather || {};
  const news = cfg.news || {};

  setValue('s-provider', llm.provider || 'ollama');
  setValue('s-briefing-provider', llm.briefing_provider || '');
  setValue('s-ollama-url', llm.ollama_url || '');
  setValue('s-ollama-model', llm.model || '');
  setValue('s-detection-model', llm.detection_model || '');

  // API keys: show masked value as placeholder, input stays blank
  setPlaceholder('s-anthropic', cfg.anthropic_api_key || '');
  setPlaceholder('s-openai', cfg.openai_api_key || '');
  setPlaceholder('s-gemini', cfg.gemini_api_key || '');
  setPlaceholder('s-groq', cfg.groq_api_key || '');
  setPlaceholder('s-weather-key', weather.api_key || '');
  setPlaceholder('s-news-key', news.api_key || '');
  setPlaceholder('s-todoist', (cfg.todoist || {}).api_token || '');
  setPlaceholder('s-govee', (cfg.govee || {}).api_key || '');

  document.getElementById('s-briefing-enabled').checked = !!briefing.enabled;
  setValue('s-briefing-time', briefing.time || '07:00');
  setValue('s-briefing-tz', briefing.timezone || 'America/New_York');
  document.getElementById('s-evening-enabled').checked = !!briefing.evening_enabled;
  setValue('s-evening-time', briefing.evening_time || '18:00');
  document.getElementById('s-weekly-enabled').checked = !!briefing.weekly_enabled;
  setValue('s-weekly-day', briefing.weekly_day || 'sunday');
  setValue('s-weekly-time', briefing.weekly_time || '09:00');

  setValue('s-weather-city', weather.city || '');
  setValue('s-weather-units', weather.units || 'imperial');

  const topics = Array.isArray(news.topics) ? news.topics.join(', ') : (news.topics || '');
  setValue('s-news-topics', topics);

  setValue('s-ntfy', (cfg.notifications || {}).ntfy_topic || '');

  // Voice
  const stt = cfg.stt || {};
  const tts = cfg.tts || {};
  document.getElementById('s-stt-enabled').checked = !!stt.enabled;
  setValue('s-stt-model', stt.model || 'base');
  setValue('s-stt-device', stt.device || 'cpu');
  document.getElementById('s-tts-enabled').checked = !!tts.enabled;
  setValue('s-tts-voice', tts.voice || 'af_heart');
  document.getElementById('s-tts-speed').value = tts.speed ?? 1.0;

  // Calendar write (CalDAV)
  const cal = cfg.calendar || {};
  setValue('s-caldav-url', cal.caldav_url || '');
  setValue('s-caldav-username', cal.caldav_username || '');
  setPlaceholder('s-caldav-password', cal.caldav_password || '');

  // Notes folders
  const folders = Array.isArray(cfg.notes_folders) ? cfg.notes_folders : [];
  const foldersEl = document.getElementById('s-notes-folders');
  foldersEl.innerHTML = '';
  for (const path of folders) addFolderRow(path);
}

function addFolderRow(path = '') {
  const row = document.createElement('div');
  row.className = 'flex gap-2';
  const input = document.createElement('input');
  input.type = 'text';
  input.value = path;
  input.placeholder = 'C:\\Users\\you\\Notes\\activity';
  input.className = 'form-input flex-1 text-sm font-mono';
  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.textContent = '×';
  removeBtn.className = 'px-2 text-gray-600 hover:text-red-400 transition-colors text-lg leading-none flex-shrink-0';
  removeBtn.addEventListener('click', () => row.remove());
  row.appendChild(input);
  row.appendChild(removeBtn);
  document.getElementById('s-notes-folders').appendChild(row);
}

function setValue(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  if (el.tagName === 'SELECT') el.value = val;
  else el.value = val;
}

function setPlaceholder(id, masked) {
  const el = document.getElementById(id);
  if (!el) return;
  el.placeholder = masked || 'Not configured';
  el.value = '';
}

// --- Build config to save ---

function buildUpdatedConfig() {
  // Start from the original (full, unmasked) config
  const cfg = JSON.parse(JSON.stringify(_originalConfig));

  // LLM
  cfg.llm = cfg.llm || {};
  cfg.llm.provider = document.getElementById('s-provider').value;
  cfg.llm.ollama_url = document.getElementById('s-ollama-url').value.trim() || cfg.llm.ollama_url;
  cfg.llm.model = document.getElementById('s-ollama-model').value.trim() || cfg.llm.model;
  const bProvider = document.getElementById('s-briefing-provider').value;
  if (bProvider) cfg.llm.briefing_provider = bProvider;
  else delete cfg.llm.briefing_provider;

  // API keys — only update if user typed something new (not blank, not the masked placeholder)
  function maybeUpdateKey(inputId, cfgKey, nested) {
    const val = document.getElementById(inputId).value.trim();
    if (!val) return; // blank = keep existing
    if (nested) {
      const [section, field] = nested;
      cfg[section] = cfg[section] || {};
      cfg[section][field] = val;
    } else {
      cfg[cfgKey] = val;
    }
  }

  maybeUpdateKey('s-anthropic', 'anthropic_api_key');
  maybeUpdateKey('s-openai', 'openai_api_key');
  maybeUpdateKey('s-gemini', 'gemini_api_key');
  maybeUpdateKey('s-groq', 'groq_api_key');
  maybeUpdateKey('s-weather-key', null, ['weather', 'api_key']);
  maybeUpdateKey('s-news-key', null, ['news', 'api_key']);
  maybeUpdateKey('s-todoist', null, ['todoist', 'api_token']);
  maybeUpdateKey('s-govee', null, ['govee', 'api_key']);

  // Detection model
  const detModel = document.getElementById('s-detection-model').value.trim();
  if (detModel) cfg.llm.detection_model = detModel;
  else delete cfg.llm.detection_model;

  // Briefing
  cfg.briefing = cfg.briefing || {};
  cfg.briefing.enabled = document.getElementById('s-briefing-enabled').checked;
  cfg.briefing.time = document.getElementById('s-briefing-time').value || '07:00';
  cfg.briefing.timezone = document.getElementById('s-briefing-tz').value.trim() || 'America/New_York';
  cfg.briefing.evening_enabled = document.getElementById('s-evening-enabled').checked;
  cfg.briefing.evening_time = document.getElementById('s-evening-time').value || '18:00';
  cfg.briefing.weekly_enabled = document.getElementById('s-weekly-enabled').checked;
  cfg.briefing.weekly_day = document.getElementById('s-weekly-day').value;
  cfg.briefing.weekly_time = document.getElementById('s-weekly-time').value || '09:00';

  // Weather
  cfg.weather = cfg.weather || {};
  cfg.weather.city = document.getElementById('s-weather-city').value.trim() || cfg.weather.city;
  cfg.weather.units = document.getElementById('s-weather-units').value;

  // News
  cfg.news = cfg.news || {};
  const topicsRaw = document.getElementById('s-news-topics').value;
  cfg.news.topics = topicsRaw.split(',').map(t => t.trim()).filter(Boolean);

  // ntfy
  cfg.notifications = cfg.notifications || {};
  const ntfy = document.getElementById('s-ntfy').value.trim();
  if (ntfy) cfg.notifications.ntfy_topic = ntfy;

  // Voice
  cfg.stt = {
    enabled: document.getElementById('s-stt-enabled').checked,
    model: document.getElementById('s-stt-model').value,
    device: document.getElementById('s-stt-device').value,
    compute_type: document.getElementById('s-stt-device').value === 'cuda' ? 'float16' : 'int8',
  };
  cfg.tts = {
    enabled: document.getElementById('s-tts-enabled').checked,
    voice: document.getElementById('s-tts-voice').value,
    speed: parseFloat(document.getElementById('s-tts-speed').value) || 1.0,
  };

  // Calendar write (CalDAV)
  cfg.calendar = cfg.calendar || {};
  const caldavUrl = document.getElementById('s-caldav-url').value.trim();
  if (caldavUrl) cfg.calendar.caldav_url = caldavUrl;
  const caldavUser = document.getElementById('s-caldav-username').value.trim();
  if (caldavUser) cfg.calendar.caldav_username = caldavUser;
  maybeUpdateKey('s-caldav-password', null, ['calendar', 'caldav_password']);

  // Notes folders
  const folderInputs = document.querySelectorAll('#s-notes-folders input');
  cfg.notes_folders = Array.from(folderInputs).map(i => i.value.trim()).filter(Boolean);

  return cfg;
}

// --- Save ---

document.getElementById('s-notes-add').addEventListener('click', () => addFolderRow());

document.getElementById('save-btn').addEventListener('click', async () => {
  const btn = document.getElementById('save-btn');
  const status = document.getElementById('save-status');
  btn.disabled = true;
  btn.textContent = 'Saving…';
  status.textContent = '';

  const cfg = buildUpdatedConfig();

  try {
    await fetch('/api/setup/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    });
  } catch {
    // Server closes connection on restart — expected
  }

  status.textContent = 'Restarting server…';
  let attempts = 0;
  const poll = setInterval(async () => {
    attempts++;
    try {
      const res = await fetch('/health');
      if (res.ok) {
        clearInterval(poll);
        status.textContent = 'Saved! Redirecting…';
        setTimeout(() => { window.location.href = '/'; }, 600);
      }
    } catch {}
    if (attempts >= 30) {
      clearInterval(poll);
      btn.disabled = false;
      btn.textContent = 'Save & restart';
      status.textContent = 'Taking longer than expected — try refreshing.';
    }
  }, 1000);
});

loadConfig();
