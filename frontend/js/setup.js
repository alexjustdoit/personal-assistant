const TOTAL_STEPS = 5;
let currentStep = 1;

// --- Step rendering ---

function renderStepIndicators() {
  const container = document.getElementById('step-indicators');
  container.innerHTML = '';
  for (let i = 1; i <= TOTAL_STEPS; i++) {
    const dot = document.createElement('div');
    const isActive = i === currentStep;
    const isDone = i < currentStep;
    dot.className = [
      'step-dot',
      isActive ? 'step-dot-active' : isDone ? 'step-dot-done' : 'step-dot-inactive',
    ].join(' ');
    container.appendChild(dot);
    if (i < TOTAL_STEPS) {
      const line = document.createElement('div');
      line.className = 'step-line ' + (isDone ? 'step-line-done' : 'step-line-inactive');
      container.appendChild(line);
    }
  }
}

function showStep(n) {
  document.querySelectorAll('.step-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById(`step-${n}`).classList.remove('hidden');

  const backBtn = document.getElementById('back-btn');
  const nextBtn = document.getElementById('next-btn');
  const navDiv = document.getElementById('nav-buttons');

  backBtn.classList.toggle('hidden', n === 1);

  if (n === TOTAL_STEPS) {
    nextBtn.classList.add('hidden');
    navDiv.classList.add('hidden');
  } else {
    nextBtn.classList.remove('hidden');
    navDiv.classList.remove('hidden');
    nextBtn.textContent = n === TOTAL_STEPS - 1 ? 'Review →' : 'Continue →';
  }

  renderStepIndicators();
}

function goNext() {
  if (currentStep < TOTAL_STEPS) {
    currentStep++;
    showStep(currentStep);
  }
}

function goBack() {
  if (currentStep > 1) {
    currentStep--;
    showStep(currentStep);
  }
}

document.getElementById('next-btn').addEventListener('click', goNext);
document.getElementById('back-btn').addEventListener('click', goBack);

// --- Ollama test ---

document.getElementById('test-ollama-btn').addEventListener('click', async () => {
  const btn = document.getElementById('test-ollama-btn');
  const result = document.getElementById('ollama-test-result');
  const url = document.getElementById('ollama-url').value.trim();
  const model = document.getElementById('ollama-model').value.trim();

  btn.disabled = true;
  btn.textContent = 'Testing…';
  result.textContent = '';
  result.className = 'text-sm';

  try {
    const res = await fetch('/api/setup/test-ollama', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, model }),
    });
    const data = await res.json();

    if (data.connected && data.model_available) {
      result.textContent = '✓ Connected — model found';
      result.className = 'text-sm text-green-400';
    } else if (data.connected && !data.model_available) {
      const available = data.models.length ? data.models.join(', ') : 'none found';
      result.textContent = `⚠ Connected but model not found. Available: ${available}`;
      result.className = 'text-sm text-yellow-400';
    } else {
      result.textContent = '✗ Could not connect to Ollama';
      result.className = 'text-sm text-red-400';
    }
  } catch {
    result.textContent = '✗ Request failed';
    result.className = 'text-sm text-red-400';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Test connection';
  }
});

// --- Briefing fields toggle ---

document.getElementById('briefing-enabled').addEventListener('change', (e) => {
  document.getElementById('briefing-fields').style.opacity = e.target.checked ? '1' : '0.4';
  document.getElementById('briefing-fields').style.pointerEvents = e.target.checked ? '' : 'none';
});

document.getElementById('evening-enabled').addEventListener('change', (e) => {
  document.getElementById('evening-fields').style.opacity = e.target.checked ? '1' : '0.4';
  document.getElementById('evening-fields').style.pointerEvents = e.target.checked ? '' : 'none';
});

// --- Second calendar URL ---

document.getElementById('add-calendar-btn').addEventListener('click', () => {
  const row2 = document.getElementById('calendar-url-2');
  row2.style.display = '';
  document.getElementById('add-calendar-btn').style.display = 'none';
});

// --- Build config object ---

function buildConfig() {
  const topicsRaw = document.getElementById('news-topics').value;
  const topics = topicsRaw.split(',').map(t => t.trim()).filter(Boolean);

  const calUrls = Array.from(document.querySelectorAll('.calendar-url-input'))
    .map(el => el.value.trim())
    .filter(Boolean);
  const todoistToken = document.getElementById('todoist-token').value.trim();
  const goveeKey = document.getElementById('govee-key').value.trim();
  const weatherKey = document.getElementById('weather-key').value.trim();
  const newsKey = document.getElementById('news-key').value.trim();
  const ntfyTopic = document.getElementById('ntfy-topic').value.trim();
  const anthropicKey = document.getElementById('anthropic-key').value.trim();
  const openaiKey = document.getElementById('openai-key').value.trim();
  const geminiKey = document.getElementById('gemini-key').value.trim();
  const groqKey = document.getElementById('groq-key').value.trim();
  const briefingProvider = document.getElementById('briefing-provider').value;

  // quality_model: prefer best available cloud, otherwise ollama
  let qualityModel = 'ollama';
  if (geminiKey) qualityModel = 'gemini';
  else if (anthropicKey) qualityModel = 'claude';
  else if (openaiKey) qualityModel = 'openai';
  else if (groqKey) qualityModel = 'groq';

  return {
    server: { host: '0.0.0.0', port: 8000 },
    llm: {
      provider: document.getElementById('default-provider').value,
      model: document.getElementById('ollama-model').value.trim() || 'llama3.1:8b',
      ollama_url: document.getElementById('ollama-url').value.trim() || 'http://localhost:11434',
      quality_model: qualityModel,
      ...(briefingProvider && { briefing_provider: briefingProvider }),
    },
    stt: {
      enabled: document.getElementById('stt-enabled').checked,
      model: document.getElementById('stt-model').value,
      device: document.getElementById('stt-device').value,
      compute_type: document.getElementById('stt-device').value === 'cuda' ? 'float16' : 'int8',
    },
    tts: {
      enabled: document.getElementById('tts-enabled').checked,
      voice: document.getElementById('tts-voice').value,
      speed: parseFloat(document.getElementById('tts-speed').value) || 1.0,
    },
    briefing: {
      enabled: document.getElementById('briefing-enabled').checked,
      time: document.getElementById('briefing-time').value || '07:00',
      timezone: document.getElementById('briefing-tz').value.trim() || 'America/New_York',
      evening_enabled: document.getElementById('evening-enabled').checked,
      evening_time: document.getElementById('evening-time').value || '18:00',
    },
    weather: {
      enabled: !!weatherKey,
      api_key: weatherKey,
      city: document.getElementById('weather-city').value.trim() || 'New York,US',
      units: document.getElementById('weather-units').value,
    },
    calendar: {
      enabled: calUrls.length > 0,
      ical_urls: calUrls,
    },
    news: {
      enabled: !!newsKey,
      api_key: newsKey,
      topics,
    },
    notifications: {
      ntfy_url: 'https://ntfy.sh',
      ntfy_topic: ntfyTopic,
    },
    todoist: { api_token: todoistToken },
    govee: { api_key: goveeKey },
    claude_memory: { path: '' },
    notes_folders: [],
    activity_tracking: {
      enabled: false,
      log_folder: '',
      poll_interval_minutes: 30,
      eod_summary_time: '22:00',
      ignored_domains: [],
    },
    anthropic_api_key: anthropicKey,
    openai_api_key: openaiKey,
    openai_model: 'gpt-5.4-nano',
    gemini_api_key: geminiKey,
    groq_api_key: groqKey,
  };
}

// --- Launch ---

document.getElementById('launch-btn').addEventListener('click', async () => {
  document.getElementById('step5-ready').classList.add('hidden');
  document.getElementById('step5-restarting').classList.remove('hidden');

  const config = buildConfig();

  try {
    await fetch('/api/setup/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
  } catch {
    // Server may close the connection when it restarts — that's expected
  }

  const statusEl = document.getElementById('restart-status');
  let attempts = 0;

  const poll = setInterval(async () => {
    attempts++;
    statusEl.textContent = `Waiting for server… (${attempts}s)`;
    try {
      const res = await fetch('/health');
      if (res.ok) {
        clearInterval(poll);
        statusEl.textContent = 'Ready! Redirecting…';
        setTimeout(() => { window.location.href = '/'; }, 800);
      }
    } catch {
      // still restarting
    }
    if (attempts >= 30) {
      clearInterval(poll);
      statusEl.textContent = 'Taking longer than expected. Try refreshing the page.';
    }
  }, 1000);
});

// --- Init ---

showStep(1);
