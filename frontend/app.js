/* =========================================================
   J.A.R.V.I.S. INTERFACE CONTROLLER
   - Real System Hardware Telemetry
   - Real Activity Event Logger
   - LiveKit WebRTC Voice & Data Connection
   ========================================================= */

let room = null;
let isProcessing = false;
let isMicActive = false;

document.addEventListener('DOMContentLoaded', () => {
  initClock();
  initGlobeCanvas();
  initWaveformVisualizer();
  initLandscapeGrid();
  initInteractionConsole();
  initRealSystemMetrics();
  initLiveKitConnection();
});

/* =========================================================
   LIVE CLOCK & DATE
   ========================================================= */
function initClock() {
  const timeEl = document.getElementById('current-time');
  const dateEl = document.getElementById('current-date');

  function update() {
    const now = new Date();
    let hours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    timeEl.textContent = `${String(hours).padStart(2, '0')}:${minutes} ${ampm}`;

    const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
    const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    dateEl.textContent = `${days[now.getDay()]}, ${String(now.getDate()).padStart(2, '0')} ${months[now.getMonth()]} ${now.getFullYear()}`;
  }
  update();
  setInterval(update, 1000);
}

/* =========================================================
   REAL HARDWARE TELEMETRY POLLING (CPU, RAM, DISK, BATTERY)
   ========================================================= */
function initRealSystemMetrics() {
  const cpuBar = document.getElementById('cpu-bar');
  const cpuVal = document.getElementById('cpu-val');
  const ramBar = document.getElementById('ram-bar');
  const ramVal = document.getElementById('ram-val');
  const diskBar = document.getElementById('disk-bar');
  const diskVal = document.getElementById('disk-val');
  const netBar = document.getElementById('net-bar');
  const netVal = document.getElementById('net-val');
  
  const powerCircle = document.getElementById('power-circle');
  const powerText = document.getElementById('power-percent');
  const powerStatusLabel = document.getElementById('power-status-label');

  async function fetchStats() {
    try {
      const res = await fetch('/api/system-stats');
      if (!res.ok) return;
      const data = await res.json();

      // 1. Real CPU
      const cpu = Math.round(data.cpu);
      cpuBar.style.width = `${cpu}%`;
      cpuVal.textContent = `${cpu}%`;

      // 2. Real RAM
      const ram = Math.round(data.ram);
      ramBar.style.width = `${ram}%`;
      ramVal.textContent = `${ram}%`;

      // 3. Real Disk
      const disk = Math.round(data.disk);
      diskBar.style.width = `${disk}%`;
      diskVal.textContent = `${disk}%`;

      // 4. Real Network
      netVal.textContent = data.network;
      netVal.className = `stat-pct ${data.network === 'STABLE' ? 'green-text' : ''}`;
      netBar.style.background = data.network === 'STABLE' ? 'var(--green-status)' : '#ff3333';

      // 5. Real Battery / Power Dial
      const pwr = data.power.percent;
      powerText.textContent = `${pwr}%`;
      const offset = 301.6 - (301.6 * pwr) / 100;
      powerCircle.style.strokeDashoffset = offset;
      powerStatusLabel.textContent = data.power.status;

    } catch (err) {
      console.warn('Telemetry poll error:', err);
    }
  }

  fetchStats();
  setInterval(fetchStats, 2000); // Polling interval: 2 seconds
}

/* =========================================================
   REAL ACTIVITY EVENT LOGGER
   ========================================================= */
function addActivityLog(text, iconType = 'info') {
  const logList = document.getElementById('activity-log');
  if (!logList) return;

  const now = new Date();
  let hours = now.getHours() % 12 || 12;
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const ampm = now.getHours() >= 12 ? 'PM' : 'AM';
  const timeStr = `${String(hours).padStart(2, '0')}:${minutes} ${ampm}`;

  let iconSvg = '';
  if (iconType === 'voice') {
    iconSvg = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/></svg>';
  } else if (iconType === 'tool') {
    iconSvg = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"/></svg>';
  } else {
    iconSvg = '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8"/></svg>';
  }

  const li = document.createElement('li');
  li.className = 'activity-item';
  li.innerHTML = `
    <span class="act-icon">${iconSvg}</span>
    <span class="act-title">${text}</span>
    <span class="act-time">${timeStr}</span>
  `;

  logList.insertBefore(li, logList.firstChild);
  if (logList.children.length > 6) {
    logList.removeChild(logList.lastChild);
  }
}

// Initial bootstrap activities
addActivityLog('System HUD Booted');
addActivityLog('Telemetry Sensors Online');

/* =========================================================
   LIVEKIT WEBRTC AGENT LINK
   ========================================================= */
async function initLiveKitConnection() {
  const statusMain = document.getElementById('jarvis-status-text');
  const statusSub = document.getElementById('jarvis-sub-text');
  const voiceBtn = document.getElementById('voice-btn');

  statusMain.textContent = 'CONNECTING';
  statusSub.textContent = 'LINKING LOCAL CORE...';

  try {
    const res = await fetch('/api/token');
    const data = await res.json();

    room = new LivekitClient.Room({
      adaptiveStream: true,
      dynacast: true,
    });

    await room.connect(data.url, data.token);

    statusMain.textContent = 'READY';
    statusSub.textContent = "I'M LISTENING...";
    addActivityLog('Linked to LiveKit Core', 'tool');

    // Auto-enable Mic
    await room.localParticipant.setMicrophoneEnabled(true);
    isMicActive = true;
    voiceBtn.style.background = 'var(--cyan-primary)';
    voiceBtn.style.color = '#000';
    addActivityLog('Microphone Stream Published', 'voice');

    // Handle Jarvis Voice Output
    room.on(LivekitClient.RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === LivekitClient.Track.Kind.Audio) {
        const audioEl = track.attach();
        audioEl.style.display = 'none';
        document.body.appendChild(audioEl);

        statusMain.textContent = 'SPEAKING';
        statusSub.textContent = 'JARVIS TRANSMITTING';
        isProcessing = true;
        addActivityLog('Jarvis Spoke Response', 'voice');
      }
    });

    room.on(LivekitClient.RoomEvent.TrackUnsubscribed, (track) => {
      track.detach().forEach(el => el.remove());
      statusMain.textContent = 'READY';
      statusSub.textContent = "I'M LISTENING...";
      isProcessing = false;
    });

    // Handle Backend Tool Execution & Data Packets
    room.on(LivekitClient.RoomEvent.DataReceived, (payload) => {
      try {
        const msg = JSON.parse(new TextDecoder().decode(payload));
        if (msg.task || msg.action) {
          addActivityLog(msg.task || msg.action, 'tool');
        }
      } catch (e) {}
    });

  } catch (err) {
    console.error('LiveKit connection error:', err);
    statusMain.textContent = 'OFFLINE';
    statusSub.textContent = 'CORE CONNECTION FAILED';
  }
}

/* =========================================================
   3D HOLOGRAPHIC EARTH CANVAS
   ========================================================= */
function initGlobeCanvas() {
  const canvas = document.getElementById('globe-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const width = canvas.width;
  const height = canvas.height;
  const cx = width / 2;
  const cy = height / 2;
  const radius = 68;
  let angle = 0;

  const landNodes = [
    [52, -105], [48, -95], [38, -98], [35, -82], [58, -120], [64, -150], [28, -100],
    [-5, -60], [-15, -55], [-25, -50], [-35, -65], [5, -75],
    [52, 10], [48, 2], [55, 38], [40, -4], [60, 25],
    [10, 20], [0, 25], [-15, 28], [-28, 24], [25, 12], [4, 40],
    [55, 80], [60, 100], [35, 105], [25, 80], [40, 115], [22, 100], [12, 105], [58, 140],
    [-25, 135], [-32, 145], [-20, 120]
  ];

  const particles = [];
  landNodes.forEach(([lat, lon]) => {
    particles.push({ lat, lon });
    for (let i = 0; i < 14; i++) {
      particles.push({
        lat: lat + (Math.random() - 0.5) * 12,
        lon: lon + (Math.random() - 0.5) * 16
      });
    }
  });

  function renderGlobe() {
    ctx.clearRect(0, 0, width, height);

    const glow = ctx.createRadialGradient(cx, cy, radius * 0.7, cx, cy, radius * 1.3);
    glow.addColorStop(0, 'rgba(0, 243, 255, 0.0)');
    glow.addColorStop(0.75, 'rgba(0, 243, 255, 0.16)');
    glow.addColorStop(1, 'transparent');
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, radius * 1.3, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = 'rgba(0, 243, 255, 0.45)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.stroke();

    for (let lat = -60; lat <= 60; lat += 30) {
      const latRad = lat * Math.PI / 180;
      const y = cy - Math.sin(latRad) * radius;
      const r = Math.cos(latRad) * radius;
      ctx.strokeStyle = 'rgba(0, 243, 255, 0.12)';
      ctx.beginPath();
      ctx.ellipse(cx, y, r, r * 0.22, 0, 0, Math.PI * 2);
      ctx.stroke();
    }

    particles.forEach(p => {
      const latR = p.lat * Math.PI / 180;
      const lonR = (p.lon + angle) * Math.PI / 180;

      const x = radius * Math.cos(latR) * Math.sin(lonR);
      const y = -radius * Math.sin(latR);
      const z = radius * Math.cos(latR) * Math.cos(lonR);

      if (z > 0) {
        const depthAlpha = z / radius;
        ctx.fillStyle = `rgba(0, 243, 255, ${0.3 + depthAlpha * 0.7})`;
        ctx.shadowColor = '#00f3ff';
        ctx.shadowBlur = 4;
        ctx.beginPath();
        ctx.arc(cx + x, cy + y, 1.4, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    });

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(0.32);
    ctx.strokeStyle = 'rgba(255, 85, 0, 0.45)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.ellipse(0, 0, radius * 1.38, radius * 0.52, 0, 0, Math.PI * 2);
    ctx.stroke();

    const satAngle = -angle * 2.2 * Math.PI / 180;
    const satX = radius * 1.38 * Math.cos(satAngle);
    const satY = radius * 0.52 * Math.sin(satAngle);
    ctx.fillStyle = '#ff5500';
    ctx.shadowColor = '#ff5500';
    ctx.shadowBlur = 9;
    ctx.beginPath();
    ctx.arc(satX, satY, 3.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    angle = (angle + 0.45) % 360;
    requestAnimationFrame(renderGlobe);
  }

  renderGlobe();
}

/* =========================================================
   AUDIO WAVEFORM VISUALIZER
   ========================================================= */
function initWaveformVisualizer() {
  const canvas = document.getElementById('waveform-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;

  let step = 0;
  function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const bars = 48;
    const barWidth = 3;
    const spacing = (canvas.width - bars * barWidth) / (bars - 1);
    ctx.fillStyle = '#00f3ff';

    for (let i = 0; i < bars; i++) {
      let amp = Math.sin(i * 0.2 + step) * Math.cos(i * 0.05 + step * 0.5);
      if (isProcessing) amp *= 2.2;
      const barHeight = Math.max(3, Math.abs(amp) * (canvas.height * 0.75));
      ctx.fillRect(i * (barWidth + spacing), canvas.height / 2 - barHeight / 2, barWidth, barHeight);
    }
    step += isProcessing ? 0.18 : 0.06;
    requestAnimationFrame(render);
  }
  render();
}

/* WIREFRAME LANDSCAPE */
function initLandscapeGrid() {
  const canvas = document.getElementById('landscape-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = 120;
  canvas.height = 70;

  ctx.strokeStyle = 'rgba(0, 243, 255, 0.4)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(10, 60);
  ctx.lineTo(40, 25);
  ctx.lineTo(65, 45);
  ctx.lineTo(95, 15);
  ctx.lineTo(120, 60);
  ctx.stroke();
}

/* CONSOLE INTERACTION */
function initInteractionConsole() {
  const inputEl = document.getElementById('ai-input');
  const sendBtn = document.getElementById('send-btn');
  const voiceBtn = document.getElementById('voice-btn');
  const clearBtn = document.getElementById('clear-act-btn');

  // Text message publishing over LiveKit Reliable Data Channel
  async function handleSend() {
    const text = inputEl.value.trim();
    if (!text || !room) return;
    inputEl.value = '';

    addActivityLog(`Command: "${text}"`, 'voice');
    document.getElementById('jarvis-status-text').textContent = 'PROCESSING';
    document.getElementById('jarvis-sub-text').textContent = 'EXECUTING TASK...';

    const payload = new TextEncoder().encode(JSON.stringify({ text }));
    await room.localParticipant.publishData(payload, { reliable: true });
  }

  // Mic toggle handler
  voiceBtn.addEventListener('click', async () => {
    if (!room) return;
    isMicActive = !isMicActive;
    await room.localParticipant.setMicrophoneEnabled(isMicActive);
    voiceBtn.style.background = isMicActive ? 'var(--cyan-primary)' : 'rgba(0, 243, 255, 0.15)';
    voiceBtn.style.color = isMicActive ? '#000' : 'var(--cyan-primary)';
    addActivityLog(isMicActive ? 'Microphone Resumed' : 'Microphone Muted', 'voice');
  });

  if (clearBtn) {
    clearBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const logList = document.getElementById('activity-log');
      if (logList) logList.innerHTML = '';
      addActivityLog('Activity Log Cleared');
    });
  }

  sendBtn.addEventListener('click', handleSend);
  inputEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleSend(); });
}