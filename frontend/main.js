// frontend/main.js
const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');
const fs = require('fs');

const ROOT_DIR = __dirname;                 // frontend/
const REPO_DIR = path.join(ROOT_DIR, '..'); // repo root
const DATA_DIR = path.join(REPO_DIR, 'LunaData');
const SETTINGS_PATH = path.join(DATA_DIR, 'settings.json');

function readJsonSafe(p, def = {}) {
  try {
    if (!fs.existsSync(p)) return def;
    const x = JSON.parse(fs.readFileSync(p, 'utf8'));
    return (x && typeof x === 'object') ? x : def;
  } catch { return def; }
}
function writeJsonMerge(p, patch) {
  try {
    fs.mkdirSync(path.dirname(p), { recursive: true });
    const cur = readJsonSafe(p, {});
    const out = { ...cur, ...patch };
    fs.writeFileSync(p, JSON.stringify(out, null, 2), 'utf8');
    return out;
  } catch { /* ignore */ }
}

function workArea() {
  return screen.getPrimaryDisplay().workArea; // {x,y,width,height}
}

/** 计算预设尺寸：small=220，medium=¼屏面积的正方形，large=½屏面积的正方形 */
function getPresetSize(kind = 'medium') {
  const wa = workArea();
  if (kind === 'small') {
    const side = 400; // 你要求“原中号当小号”
    return { w: side, h: side };
  }
  if (kind === 'large') {
    // 半屏面积：s = sqrt(0.5 * W * H)
    const side = Math.max(150, Math.floor(Math.sqrt(0.5 * wa.width * wa.height)));
    return { w: side, h: side };
  }
  // medium：四分之一屏面积：s = sqrt(0.25 * W * H)
  const side = Math.max(150, Math.floor(Math.sqrt(0.25 * wa.width * wa.height)));
  return { w: side, h: side };
}

function clampToWorkArea(x, y, w, h) {
  const wa = workArea();
  const minX = wa.x, minY = wa.y;
  const maxX = wa.x + Math.max(0, wa.width  - w);
  const maxY = wa.y + Math.max(0, wa.height - h);
  const ox = Math.min(Math.max(x, minX), maxX);
  const oy = Math.min(Math.max(y, minY), maxY);
  return { x: ox, y: oy };
}

let win = null;

function createWindow () {
  const settings = readJsonSafe(SETTINGS_PATH, {});
  const preset = (settings.window_size_preset || 'medium');
  const size   = getPresetSize(preset);

  // 位置还原（带边界修正；默认右下角留 24px）
  let x, y;
  const pos = settings.window_position;
  if (pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) {
    const safe = clampToWorkArea(pos.x, pos.y, size.w, size.h);
    x = safe.x; y = safe.y;
  } else {
    const wa = workArea();
    x = wa.x + wa.width  - size.w - 24;
    y = wa.y + wa.height - size.h - 24;
  }

    win = new BrowserWindow({
      width: size.w, height: size.h, x, y,
      useContentSize: true,
      frame: false,
      transparent: true,              // ✅ 打开透明
      backgroundColor: '#00000000',   // ✅ 全透明背景
      alwaysOnTop: true,
      resizable: true,
      hasShadow: false,
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false
      }
    });


  // 允许缩回小号
  win.setMinimumSize(150, 150);

  win.loadFile('index.html');

  // —— 拖动持久化（节流 200ms）——
  let saveT = null;
  win.on('move', () => {
    if (saveT) clearTimeout(saveT);
    saveT = setTimeout(() => {
      const [nx, ny] = win.getPosition();
      win.webContents.send('win-moved', { x: nx, y: ny });
      writeJsonMerge(SETTINGS_PATH, { window_position: { x: nx, y: ny } });
    }, 200);
  });

  // —— 尺寸预设：内容尺寸缩放 + 位置钳制 + 持久化 ——
  ipcMain.handle('set-size-preset', (_evt, presetName) => {
    const s = getPresetSize(presetName);
    if (win && !win.isDestroyed()) {
      win.setContentSize(s.w, s.h, false);     // 关键：内容尺寸，支持“变小”
      const [cx, cy] = win.getPosition();
      const [cw, ch] = win.getContentSize();
      const safe = clampToWorkArea(cx, cy, cw, ch);
      if (safe.x !== cx || safe.y !== cy) win.setPosition(safe.x, safe.y, false);
      writeJsonMerge(SETTINGS_PATH, { window_size_preset: presetName });
      return { ok: true, size: s };
    }
    return { ok: false };
  });

  // win.webContents.openDevTools({ mode: 'detach' }); // 调试时打开
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
