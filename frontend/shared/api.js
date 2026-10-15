
const JarvisAPI = {
  BASE_URL: "http://localhost:8080",

  async getSystemStats() {
    try {
      const res = await fetch(`${this.BASE_URL}/api/system-stats`);
      return res.ok ? await res.json() : null;
    } catch (err) {
      console.warn("System stats error:", err);
      return null;
    }
  },

  async getWeather() {
    try {
      const res = await fetch(`${this.BASE_URL}/api/weather`);
      return res.ok ? await res.json() : null;
    } catch (err) {
      console.warn("Weather error:", err);
      return null;
    }
  },

  async initLiveKit(onAudioTrack, onDataReceived) {
    let room = null;
    const attachedTracks = new Map();

    const attachAudioTrack = (track) => {
      if (
        !onAudioTrack ||
        !track ||
        track.kind !== LivekitClient.Track.Kind.Audio
      ) {
        return;
      }

      const key = track.sid || track;

      if (attachedTracks.has(key)) {
        return;
      }

      const audioElement = track.attach();

      audioElement.autoplay = true;
      audioElement.playsInline = true;
      audioElement.muted = false;
      audioElement.volume = 1;

      attachedTracks.set(key, audioElement);

      try {
        // Let the UI append the audio element first.
        onAudioTrack(audioElement);
      } catch (err) {
        console.error("Audio callback failed:", err);
      }

      // Explicit playback attempt.
      const playResult = audioElement.play?.();

      if (playResult?.catch) {
        playResult.catch((err) => {
          console.warn(
            "JARVIS audio playback failed:",
            err
          );
        });
      }

      console.info("JARVIS audio track attached:", key);
    };

    try {
      const res = await fetch(`${this.BASE_URL}/api/token`);

      if (!res.ok) {
        throw new Error(`Token request failed: HTTP ${res.status}`);
      }

      const data = await res.json();

      room = new LivekitClient.Room({
        adaptiveStream: true,
        dynacast: true,
      });

      // IMPORTANT: register listeners BEFORE connecting.
      room.on(
        LivekitClient.RoomEvent.TrackSubscribed,
        (track) => {
          attachAudioTrack(track);
        }
      );

      room.on(
        LivekitClient.RoomEvent.TrackUnsubscribed,
        (track) => {
          const key = track.sid || track;
          attachedTracks.delete(key);

          try {
            track.detach().forEach((element) => {
              element.remove();
            });
          } catch (err) {
            console.debug("Track cleanup skipped:", err);
          }
        }
      );

      room.on(
        LivekitClient.RoomEvent.DataReceived,
        (payload) => {
          if (!onDataReceived) return;

          try {
            const msg = JSON.parse(
              new TextDecoder().decode(payload)
            );

            onDataReceived(msg);
          } catch (err) {
            console.warn("Data message parsing failed:", err);
          }
        }
      );

      room.on(
        LivekitClient.RoomEvent.Disconnected,
        (reason) => {
          console.warn(
            "JARVIS LiveKit disconnected:",
            reason
          );
        }
      );

      await room.connect(data.url, data.token);

      console.info(
        "JARVIS LiveKit connected:",
        room.name
      );

      // Check tracks that already exist after connection.
      for (const participant of room.remoteParticipants.values()) {
        for (const publication of participant.trackPublications.values()) {
          if (publication.track) {
            attachAudioTrack(publication.track);
          }
        }
      }

      await room.localParticipant.setMicrophoneEnabled(true);

      return room;
    } catch (err) {
      console.error("LiveKit connection error:", err);

      if (room) {
        try {
          await room.disconnect();
        } catch (disconnectErr) {
          console.debug("Room cleanup failed:", disconnectErr);
        }
      }

      return null;
    }
  },
};
