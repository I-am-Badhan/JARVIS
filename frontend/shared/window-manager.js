const JarvisWindowManager = {
  getHandle() {
    if (window.__TAURI__?.window) {
      return window.__TAURI__.window.getCurrentWindow();
    }
    if (window.__TAURI__?.webviewWindow) {
      return window.__TAURI__.webviewWindow.getCurrentWebviewWindow();
    }
    return null;
  },

  init() {
    document.addEventListener('mousedown', (e) => {
      const win = JarvisWindowManager.getHandle();
      if (!win) return;

      if (e.target.closest('.win-resize-handle') && e.button === 0) {
        e.preventDefault();
        e.stopPropagation();
        if (typeof win.startResizeDragging === 'function') {
          win.startResizeDragging('SouthEast').catch(() => {});
        }
        return;
      }

      const header = e.target.closest('.widget-header');
      if (header && !e.target.closest('.win-controls') && !e.target.closest('button')) {
        if (e.button === 0) {
          if (e.detail === 2) {
            win.toggleMaximize().catch(() => {});
          } else {
            win.startDragging().catch(() => {});
          }
        }
      }
    });

    document.addEventListener('click', (e) => {
      const win = JarvisWindowManager.getHandle();
      if (!win) return;

      if (e.target.closest('.btn-minimize')) {
        e.preventDefault();
        win.minimize().catch(() => {});
      } else if (e.target.closest('.btn-maximize')) {
        e.preventDefault();
        win.toggleMaximize().catch(() => {});
      } else if (e.target.closest('.btn-close')) {
        e.preventDefault();
        win.close().catch(() => {});
      }
    });
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => JarvisWindowManager.init());
} else {
  JarvisWindowManager.init();
}