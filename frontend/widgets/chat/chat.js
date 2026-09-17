let livekitRoom = null;
const input = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const micBtn = document.getElementById('mic-btn');
const history = document.getElementById('chat-history');

function appendMessage(sender, text) {
  if (!text) return;
  const msgDiv = document.createElement('div');
  msgDiv.className = `chat-msg ${sender}`;
  msgDiv.innerHTML = `<div class="msg-bubble">${text}</div>`;
  history.appendChild(msgDiv);
  history.scrollTop = history.scrollHeight;
}

JarvisAPI.initLiveKit(
  (audioEl) => {
    document.body.appendChild(audioEl);
    JarvisBus.emit('AI_SPEAKING', true);
    audioEl.onended = () => JarvisBus.emit('AI_SPEAKING', false);
  },
  (data) => {
    if (data.sender === 'user' && data.text) {
      appendMessage('user', data.text);
    } else if (data.reply || (data.sender === 'jarvis' && data.text)) {
      appendMessage('jarvis', data.reply || data.text);
    }
  }
).then((room) => {
  livekitRoom = room;
});

function handleSend() {
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  appendMessage('user', text);

  if (livekitRoom && livekitRoom.state === 'connected') {
    const payload = new TextEncoder().encode(JSON.stringify({ text }));
    livekitRoom.localParticipant.publishData(payload, { reliable: true });
  } else {
    console.warn("LiveKit Room is not connected yet.");
  }
}

sendBtn.addEventListener('click', handleSend);
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleSend();
});

let micEnabled = true;
if (micBtn) {
  micBtn.addEventListener('click', async () => {
    if (!livekitRoom) return;
    micEnabled = !micEnabled;
    await livekitRoom.localParticipant.setMicrophoneEnabled(micEnabled);
    micBtn.style.opacity = micEnabled ? "1" : "0.4";
  });
}