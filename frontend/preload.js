// frontend/preload.js
const { contextBridge, ipcRenderer } = require('electron');
const fs = require('fs');
const path = require('path');

// ====== 暴露后端 API 根 ======
let apiUrl = 'http://127.0.0.1:8000';
try {
  const root = path.join(__dirname, '..');
  const cfgPath = path.join(root, 'config.json');
  if (fs.existsSync(cfgPath)) {
    const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    if (cfg && typeof cfg.LUNA_API === 'string' && cfg.LUNA_API.trim()) {
      apiUrl = cfg.LUNA_API.trim();
      console.log('[Preload] LUNA_API from config.json:', apiUrl);
    }
  }
} catch (e) {
  console.log('[Preload] read config.json failed, fallback to default:', apiUrl);
}
if (process.env.LUNA_API && process.env.LUNA_API.trim()) {
  apiUrl = process.env.LUNA_API.trim();
  console.log('[Preload] LUNA_API from env:', apiUrl);
}
contextBridge.exposeInMainWorld('LUNA_API', apiUrl);
console.log('[Preload] LUNA_API exposed:', apiUrl);

// ====== 暴露窗口交互 API（拖动/尺寸预设）======
contextBridge.exposeInMainWorld('Luna', {
  onWindowMoved: (cb) => {
    if (typeof cb === 'function') {
      ipcRenderer.on('win-moved', (_e, pos) => cb(pos));
    }
  },
  setSizePreset: async (preset) => {
    return await ipcRenderer.invoke('set-size-preset', preset);
  }
});
