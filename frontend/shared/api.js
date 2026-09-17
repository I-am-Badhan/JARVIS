const JarvisAPI = {
  BASE_URL: 'http://localhost:8080',

  async getSystemStats() {
    try {
      const res = await fetch(`${this.BASE_URL}/api/system-stats`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async getWeather() {
    try {
      const res = await fetch(`${this.BASE_URL}/api/weather`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  },

  async initLiveKit(onAudioTrack, onDataReceived) {
    try {
      const res = await fetch(`${this.BASE_URL}/api/token`);
      const data = await res.json();
      const room = new LivekitClient.Room({ adaptiveStream: true, dynacast: true });
      await room.connect(data.url, data.token);
      await room.localParticipant.setMicrophoneEnabled(true);

      if (onAudioTrack) {
        room.on(LivekitClient.RoomEvent.TrackSubscribed, (track) => {
          if (track.kind === LivekitClient.Track.Kind.Audio) {
            onAudioTrack(track.attach());
          }
        });
      }

      if (onDataReceived) {
        room.on(LivekitClient.RoomEvent.DataReceived, (payload) => {
          try {
            const msg = JSON.parse(new TextDecoder().decode(payload));
            onDataReceived(msg);
          } catch (err) {}
        });
      }

      return room;
    } catch (err) {
      console.warn('LiveKit connection error:', err);
      return null;
    }
  }
};