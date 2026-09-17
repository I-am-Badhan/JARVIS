const JarvisFactory = {
  async spawn(label, url, options = {}) {
    if (!window.__TAURI__?.webviewWindow) {
      console.warn("Tauri WebviewWindow API unavailable.");
      return null;
    }
    const { WebviewWindow } = window.__TAURI__.webviewWindow;

    const existing = await WebviewWindow.getByLabel(label);
    if (existing) {
      await existing.show();
      await existing.setFocus();
      return existing;
    }

    return new WebviewWindow(label, {
      url: url,
      title: options.title || label,
      width: options.width || 450,
      height: options.height || 400,
      x: options.x || 200,
      y: options.y || 200,
      decorations: false,
      transparent: true,
      alwaysOnTop: false,
      resizable: options.resizable !== false,
      ...options
    });
  }
};