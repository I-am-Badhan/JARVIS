const JarvisBus = {
  channel: new BroadcastChannel('jarvis_internal_bus'),

  emit(event, data = {}) {
    this.channel.postMessage({ event, data });
  },

  on(event, callback) {
    this.channel.addEventListener('message', (e) => {
      if (e.data && e.data.event === event) {
        callback(e.data.data);
      }
    });
  }
};