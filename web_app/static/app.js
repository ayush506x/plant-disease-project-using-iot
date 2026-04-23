/* ═══════════════════════════════════════════════
   Tulsi Smart Plant Monitor — Real-time Client
   Socket.IO + live sensor + AI result rendering
   ═══════════════════════════════════════════════ */

// ── CLASS COLOR MAP ────────────────────────────────────────
const CLASS_COLORS = {
  healthy:   '#22c55e',
  bacterial: '#3b82f6',
  fungal:    '#f97316',
  pests:     '#a855f7',
};

// ── SOCKET.IO CONNECTION ───────────────────────────────────
const socket = io({ reconnectionDelay: 2000, reconnectionAttempts: Infinity });

socket.on('connect', () => {
  setBadge(true);
  showToast('Connected to Tulsi Monitor server ✅', 'success');
});

socket.on('disconnect', () => {
  setBadge(false);
  showToast('Connection lost — reconnecting…', 'error');
});

socket.on('connect_error', () => setBadge(false));

// ── SENSOR DATA ────────────────────────────────────────────
socket.on('sensor_update', (data) => {
  updateSensor('temp',  data.temperature, 0, 50);
  updateSensor('hum',   data.humidity,    0, 100);
  updateSensor('moist', data.moisture,    0, 100);
  updateSensor('n',     data.npk_n,       0, 200);
  updateSensor('p',     data.npk_p,       0, 200);
  updateSensor('k',     data.npk_k,       0, 200);
  updateNPKChart(data.npk_n, data.npk_p, data.npk_k);

  if (data.sensor_timestamp) {
    document.getElementById('sensor-footer').textContent =
      `Last reading: ${data.sensor_timestamp}`;
    document.getElementById('sensor-age').textContent = 'Live';
  }
  triggerAlerts(data);
});

// ── AI RESULT ──────────────────────────────────────────────
socket.on('ai_result', (data) => {
  renderAIResult(data);
});

// ── SNAPSHOT UPDATE ────────────────────────────────────────
socket.on('snapshot_update', (data) => {
  const url = data.snapshot_url + '?t=' + Date.now();
  showPlantImage(url);
  document.getElementById('cam-status').textContent = 'Live';
});

// ── SENSOR CARD UPDATER ────────────────────────────────────
function updateSensor(id, value, min, max) {
  const numEl = document.getElementById(`num-${id}`);
  const barEl = document.getElementById(`bar-${id}`);
  const cardEl = document.getElementById(`card-${id}`);

  if (value === null || value === undefined) return;

  const rounded = typeof value === 'number' ? (Number.isInteger(value) ? value : value.toFixed(1)) : value;

  // Animate number change
  animateNumber(numEl, parseFloat(numEl.textContent) || 0, parseFloat(rounded));

  // Progress bar
  const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
  barEl.style.width = pct + '%';

  // Flash animation
  cardEl.classList.remove('updated');
  void cardEl.offsetWidth; // reflow
  cardEl.classList.add('updated');
}

function animateNumber(el, from, to) {
  if (isNaN(from)) from = 0;
  const steps = 20;
  const delta = (to - from) / steps;
  let step = 0;
  const timer = setInterval(() => {
    step++;
    const current = from + delta * step;
    el.textContent = Number.isInteger(to) ? Math.round(current) : current.toFixed(1);
    if (step >= steps) {
      el.textContent = Number.isInteger(to) ? to : to.toFixed(1);
      clearInterval(timer);
    }
  }, 16);
}

// ── NPK VERTICAL CHART ─────────────────────────────────────
function updateNPKChart(n, p, k) {
  const max = 200;
  if (n !== null && n !== undefined) document.getElementById('npk-n-fill').style.height = Math.min(100, (n/max)*100) + '%';
  if (p !== null && p !== undefined) document.getElementById('npk-p-fill').style.height = Math.min(100, (p/max)*100) + '%';
  if (k !== null && k !== undefined) document.getElementById('npk-k-fill').style.height = Math.min(100, (k/max)*100) + '%';
}

// ── AI RESULT RENDERER ─────────────────────────────────────
function renderAIResult(data) {
  const label = data.label || 'Unknown';
  const conf  = data.confidence ?? 0;
  const color = CLASS_COLORS[label] || '#22c55e';

  document.getElementById('ai-emoji').textContent  = data.emoji || '🌿';
  document.getElementById('ai-label').textContent  = label.charAt(0).toUpperCase() + label.slice(1);
  document.getElementById('ai-conf').textContent   = conf.toFixed(1) + '%';
  document.getElementById('ai-advice').textContent = data.advice || '';

  if (data.ai_timestamp)
    document.getElementById('ai-timestamp').textContent = 'Analyzed: ' + data.ai_timestamp;

  // AI card class
  const aiCard = document.getElementById('ai-card');
  aiCard.classList.remove('healthy', 'disease', 'warning');
  if (label === 'healthy') aiCard.classList.add('healthy');
  else if (label === 'bacterial' || label === 'fungal') aiCard.classList.add('disease');
  else aiCard.classList.add('warning');

  // Render probability bars
  const probContainer = document.getElementById('prob-bars');
  probContainer.innerHTML = '';
  if (data.all_probs) {
    Object.entries(data.all_probs)
      .sort((a, b) => b[1] - a[1])
      .forEach(([cls, pct]) => {
        const clsColor = CLASS_COLORS[cls] || '#22c55e';
        const row = document.createElement('div');
        row.className = 'prob-row';
        row.innerHTML = `
          <span class="prob-name">${cls}</span>
          <div class="prob-track">
            <div class="prob-fill" style="width:${pct}%; background:${clsColor};"></div>
          </div>
          <span class="prob-pct">${pct}%</span>`;
        probContainer.appendChild(row);
      });
  }

  // Update health banner
  updateHealthBanner(label, conf);

  // Toast notification
  if (label !== 'healthy') {
    showToast(`⚠️ ${label.charAt(0).toUpperCase() + label.slice(1)} detected! ${conf.toFixed(1)}%`, 'warn');
  } else {
    showToast(`🌿 Plant is Healthy! (${conf.toFixed(1)}%)`, 'success');
  }
}

// ── HEALTH BANNER ──────────────────────────────────────────
function updateHealthBanner(label, conf) {
  const banner   = document.getElementById('health-banner');
  const emojiEl  = document.getElementById('health-emoji');
  const textEl   = document.getElementById('health-text');

  banner.classList.remove('health-banner--idle', 'health-banner--healthy', 'health-banner--disease', 'health-banner--warning');

  const labelCap = label.charAt(0).toUpperCase() + label.slice(1);
  if (label === 'healthy') {
    banner.classList.add('health-banner--healthy');
    emojiEl.textContent = '✅';
    textEl.textContent  = `Plant is Healthy  •  ${conf.toFixed(1)}% confidence`;
  } else if (label === 'bacterial' || label === 'fungal') {
    banner.classList.add('health-banner--disease');
    emojiEl.textContent = '🚨';
    textEl.textContent  = `${labelCap} Detected  •  ${conf.toFixed(1)}% confidence — Take action now!`;
  } else {
    banner.classList.add('health-banner--warning');
    emojiEl.textContent = '⚠️';
    textEl.textContent  = `${labelCap} Detected  •  ${conf.toFixed(1)}% confidence — Inspect plant`;
  }
}

// ── SHOW PLANT IMAGE ───────────────────────────────────────
function showPlantImage(url) {
  const img = document.getElementById('plant-image');
  const placeholder = document.getElementById('camera-placeholder');
  const frame = document.getElementById('camera-frame');
  const ts = document.getElementById('img-timestamp');

  img.onload = () => {
    img.classList.remove('hidden');
    placeholder.style.display = 'none';
    frame.classList.remove('scanning');
    ts.textContent = new Date().toLocaleTimeString();
  };
  img.src = url;
  frame.classList.add('scanning');
}

// ── ALERTS / THRESHOLDS ────────────────────────────────────
function triggerAlerts(data) {
  if (data.temperature !== null && data.temperature > 42)
    showToast('🌡️ High temperature warning: ' + data.temperature + '°C', 'warn');
  if (data.humidity !== null && data.humidity < 30)
    showToast('💧 Low humidity: ' + data.humidity + '%', 'warn');
  if (data.moisture !== null && data.moisture < 20)
    showToast('🌱 Soil is very dry: ' + data.moisture + '%', 'warn');
}

// ── BADGE ──────────────────────────────────────────────────
function setBadge(connected) {
  const badge = document.getElementById('connection-badge');
  const text  = document.getElementById('connection-text');
  badge.classList.toggle('badge--connected',    connected);
  badge.classList.toggle('badge--disconnected', !connected);
  text.textContent = connected ? 'Connected' : 'Disconnected';
}

// ── ANALYZE NOW BUTTON ─────────────────────────────────────
function requestAnalyze() {
  socket.emit('request_analyze');
  const btn = document.getElementById('btn-analyze');
  btn.textContent = '⏳ Analyzing…';
  btn.disabled = true;
  setTimeout(() => {
    btn.innerHTML = '<span>🔬</span> Analyze Now';
    btn.disabled = false;
  }, 4000);
}

// ── MANUAL IMAGE UPLOAD ────────────────────────────────────
document.getElementById('upload-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  // Show preview immediately
  const reader = new FileReader();
  reader.onload = (ev) => showPlantImage(ev.target.result);
  reader.readAsDataURL(file);

  // Upload to server for AI inference
  const form = new FormData();
  form.append('image', file);

  showToast('🔬 Uploading image for analysis…', 'success');
  document.getElementById('camera-frame').classList.add('scanning');

  try {
    const res  = await fetch('/api/analyze_upload', { method: 'POST', body: form });
    const data = await res.json();
    if (data.error) {
      showToast('❌ ' + data.error, 'error');
    } else {
      renderAIResult(data);
      // reload server snapshot
      showPlantImage('/api/snapshot?t=' + Date.now());
    }
  } catch (err) {
    showToast('❌ Upload failed: ' + err.message, 'error');
  } finally {
    document.getElementById('camera-frame').classList.remove('scanning');
  }
});

// ── LIVE CLOCK ─────────────────────────────────────────────
function updateClock() {
  document.getElementById('header-time').textContent =
    new Date().toLocaleTimeString();
}
setInterval(updateClock, 1000);
updateClock();

// ── TOAST ──────────────────────────────────────────────────
let toastTimer = null;
function showToast(msg, type = 'success') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = `toast toast--${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 4000);
}

// ── INITIAL STATUS FETCH ───────────────────────────────────
(async () => {
  try {
    const res  = await fetch('/api/status');
    const data = await res.json();
    if (data.sensors && data.sensors.temperature !== null) {
      socket.emit('_local_sensor_init'); // handled server-side on connect
    }
    if (!data.model_loaded) {
      showToast('⚠️ AI model not loaded — run train_model.py first', 'warn');
    }
  } catch {}
})();
