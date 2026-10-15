let isPlaying = false;
let currentTrackId = "";
let lastUpdatedAt = 0;
let progressSeconds = 0;
let totalTrackDuration = 240;
let progressTimer = null;
let isLiked = false;
let isShuffle = false;
let isRepeat = false;

// 1. YouTube Iframe PostMessage Controller (Array Args Required)
function sendIframeCommand(funcName, args = []) {
  const iframe = document.getElementById("ytIframe");
  if (iframe && iframe.contentWindow) {
    // Prime YouTube listener
    iframe.contentWindow.postMessage(JSON.stringify({ event: "listening" }), "*");
    // Send command with Array args
    iframe.contentWindow.postMessage(JSON.stringify({
      event: "command",
      func: funcName,
      args: Array.isArray(args) ? args : [args]
    }), "*");
  }
}

// 2. Play Execution
function executePlay(data) {
  const titleEl = document.getElementById("trackTitle");
  const artistEl = document.getElementById("trackArtist");
  const albumEl = document.getElementById("albumArt");
  const masterBtn = document.getElementById("masterPlayBtn");

  if (titleEl) titleEl.innerText = data.title;
  if (artistEl) artistEl.innerText = data.artist;
  if (albumEl && data.thumbnail) albumEl.src = data.thumbnail;
  if (masterBtn) masterBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';

  currentTrackId = data.id;
  isPlaying = true;
  progressSeconds = 0;
  totalTrackDuration = data.duration || 240;

  const iframe = document.getElementById("ytIframe");
  if (iframe && data.id) {
    iframe.src = `https://www.youtube-nocookie.com/embed/${data.id}?autoplay=1&playsinline=1&controls=0&enablejsapi=1&origin=${window.location.origin}`;
  }

  startProgressTracking();
  if (window.JarvisBus) JarvisBus.emit('MUSIC_STATE', { isPlaying: true });
}

// 3. Independent Play/Pause Controls
function pausePlayback() {
  sendIframeCommand("pauseVideo", []);
  isPlaying = false;
  const masterBtn = document.getElementById("masterPlayBtn");
  if (masterBtn) masterBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
  clearInterval(progressTimer);
  if (window.JarvisBus) JarvisBus.emit('MUSIC_STATE', { isPlaying: false });
}

function resumePlayback() {
  sendIframeCommand("playVideo", []);
  isPlaying = true;
  const masterBtn = document.getElementById("masterPlayBtn");
  if (masterBtn) masterBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
  startProgressTracking();
  if (window.JarvisBus) JarvisBus.emit('MUSIC_STATE', { isPlaying: true });
}

function notifyBackend(action) {
  fetch("/api/music/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: action })
  }).catch(() => {});
}

function togglePlayState() {
  if (isPlaying) {
    pausePlayback();
    notifyBackend("PAUSE");
  } else {
    resumePlayback();
    notifyBackend("RESUME");
  }
}

function seekRelative(secs) {
  progressSeconds = Math.max(0, Math.min(totalTrackDuration, progressSeconds + secs));
  updateProgressUI();
  sendIframeCommand("seekTo", [progressSeconds, true]);
}

function toggleLike() {
  isLiked = !isLiked;
  const btn = document.getElementById("likeBtn");
  if (btn) {
    btn.innerHTML = isLiked ? '<i class="fa-solid fa-heart"></i>' : '<i class="fa-regular fa-heart"></i>';
    btn.classList.toggle("active", isLiked);
  }
}

function toggleShuffle() {
  isShuffle = !isShuffle;
  const btn = document.getElementById("shuffleBtn");
  if (btn) btn.classList.toggle("active", isShuffle);
}

function toggleRepeat() {
  isRepeat = !isRepeat;
  const btn = document.getElementById("repeatBtn");
  if (btn) btn.classList.toggle("active", isRepeat);
}

function startProgressTracking() {
  clearInterval(progressTimer);
  progressTimer = setInterval(() => {
    if (!isPlaying) return;
    progressSeconds += 1;
    if (progressSeconds >= totalTrackDuration) {
      if (isRepeat) {
        seekRelative(-totalTrackDuration);
      } else {
        pausePlayback();
      }
    }
    updateProgressUI();
  }, 1000);
}

function updateProgressUI() {
  const pct = (progressSeconds / (totalTrackDuration || 1)) * 100;
  const fill = document.getElementById("seekFill");
  const curEl = document.getElementById("currentTime");
  const durEl = document.getElementById("totalDuration");

  if (fill) fill.style.width = pct + "%";
  if (curEl) curEl.innerText = formatTime(progressSeconds);
  if (durEl) durEl.innerText = formatTime(totalTrackDuration);
}

function handleSeek(e) {
  const track = document.getElementById("seekTrack");
  const rect = track.getBoundingClientRect();
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  progressSeconds = Math.round(totalTrackDuration * pct);
  seekRelative(0);
}

function handleVolume(e) {
  const track = document.getElementById("volumeTrack");
  const rect = track.getBoundingClientRect();
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  const vol = Math.round(pct * 100);
  const fill = document.getElementById("volumeFill");
  if (fill) fill.style.width = (pct * 100) + "%";

  sendIframeCommand("setVolume", [vol]);
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

// 4. Background State Sync Engine
async function syncMusicState() {
  try {
    const res = await fetch("/api/music/state");
    if (res.ok) {
      const data = await res.json();
      if (data && data.updated_at && data.updated_at !== lastUpdatedAt) {
        lastUpdatedAt = data.updated_at;
        if (data.action === "PLAY") {
          executePlay(data);
        } else if (data.action === "PAUSE") {
          pausePlayback();
        } else if (data.action === "RESUME") {
          resumePlayback();
        } else if (data.action === "SEEK_FORWARD") {
          seekRelative(15);
        } else if (data.action === "SEEK_BACKWARD") {
          seekRelative(-15);
        }
      }
    }
  } catch (e) {}
}

setInterval(syncMusicState, 350);
syncMusicState();

// 5. Dynamic Waveform Spectrum Canvas
const canvas = document.getElementById("waveformCanvas");
const ctx = canvas ? canvas.getContext("2d") : null;

function syncCanvasResolution() {
  if (!canvas) return;
  const rect = canvas.parentElement.getBoundingClientRect();
  if (rect.width > 0 && rect.height > 0) {
    canvas.width = rect.width;
    canvas.height = rect.height;
  }
}
window.addEventListener('resize', syncCanvasResolution);
setTimeout(syncCanvasResolution, 100);

function renderVisualizer() {
  if (!ctx || !canvas) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const midY = canvas.height / 2;

  const numBars = Math.max(26, Math.floor(canvas.width / 8));
  const barWidth = Math.max(2, Math.floor(canvas.width / (numBars * 1.8)));

  for (let i = 0; i < numBars; i++) {
    const x = i * (canvas.width / numBars);
    const distFromCenter = Math.abs(i - numBars / 2) / (numBars / 2);
    const bellFactor = Math.cos(distFromCenter * Math.PI * 0.48);

    let h = 3;
    if (isPlaying) {
      const dynamicWave = Math.sin(Date.now() / 140 + i * 0.35) * (canvas.height * 0.22) + Math.random() * (canvas.height * 0.2);
      h = Math.max(3, (dynamicWave + 8) * bellFactor);
    }

    const gradient = ctx.createLinearGradient(0, midY - h, 0, midY + h);
    gradient.addColorStop(0, '#7952ff');
    gradient.addColorStop(0.5, '#00f0ff');
    gradient.addColorStop(1, '#0088ff');

    ctx.fillStyle = gradient;
    ctx.shadowBlur = isPlaying ? 6 : 0;
    ctx.shadowColor = '#00f0ff';

    ctx.beginPath();
    ctx.roundRect(x, midY - h, barWidth, h * 2, [2]);
    ctx.fill();
  }
  requestAnimationFrame(renderVisualizer);
}
renderVisualizer();