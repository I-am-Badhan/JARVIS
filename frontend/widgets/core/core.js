function initClock() {
  const timeEl = document.getElementById('core-time');
  const dateEl = document.getElementById('core-date');
  function tick() {
    const now = new Date();
    let hours = now.getHours();
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    if (timeEl) timeEl.textContent = `${String(hours).padStart(2, '0')}:${minutes}:${seconds} ${ampm}`;

    const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
    const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    if (dateEl) dateEl.textContent = `${days[now.getDay()]}, ${String(now.getDate()).padStart(2, '0')} ${months[now.getMonth()]} ${now.getFullYear()}`;
  }
  tick();
  setInterval(tick, 1000);
}
initClock();

async function syncWeather() {
  const data = await JarvisAPI.getWeather();
  if (data) {
    document.getElementById('core-weather').textContent = data.temp;
  }
}
syncWeather();
setInterval(syncWeather, 600000);

const canvas = document.getElementById('waveform-canvas');
const ctx = canvas.getContext('2d');
let step = 0;
let isSpeaking = false;

function renderWave() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#00f3ff';
  for (let i = 0; i < 30; i++) {
    let amp = Math.sin(i * 0.3 + step) * Math.cos(i * 0.1 + step * 0.5);
    if (isSpeaking) amp *= 2.2;
    let h = Math.max(2, Math.abs(amp) * 18);
    ctx.fillRect(i * 8, 12 - h / 2, 3, h);
  }
  step += isSpeaking ? 0.16 : 0.08;
  requestAnimationFrame(renderWave);
}
renderWave();

JarvisBus.on('AI_SPEAKING', (active) => {
  isSpeaking = active;
  document.getElementById('status-text').textContent = active ? 'JARVIS SPEAKING' : 'SYSTEM READY';
});