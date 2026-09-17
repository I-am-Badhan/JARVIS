class JarvisWidget extends HTMLElement {
  connectedCallback() {
    if (this.dataset.rendered) return;
    const title = this.getAttribute('title') || 'WIDGET';
    const icon = this.getAttribute('icon') || '⚙';
    const content = this.innerHTML;

    this.innerHTML = `
      <div class="widget-frame">
        <div class="widget-header">
          <span class="widget-title">${icon} ${title}</span>
          <div class="win-controls">
            <button class="win-btn btn-minimize" title="Minimize">—</button>
            <button class="win-btn btn-maximize" title="Maximize">⤢</button>
            <button class="win-btn btn-close" title="Close">✕</button>
          </div>
        </div>
        <div class="widget-content">
          ${content}
        </div>
        <div class="win-resize-handle"></div>
      </div>
    `;
    this.dataset.rendered = "true";
  }
}
customElements.define('jarvis-widget', JarvisWidget);