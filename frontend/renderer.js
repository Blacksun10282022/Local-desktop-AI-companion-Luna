// frontend/renderer.js

// ====== API 根 ======
const API = (
  (typeof window !== 'undefined' && (window.LUNA_API || window.API || (window.env && window.env.API))) ||
  (typeof process !== 'undefined' && process.env && process.env.LUNA_API) ||
  'http://127.0.0.1:8000'
).replace(/\/$/, '');
console.log('[Renderer] API =', API);

// ====== DOM ======
const dot    = document.getElementById('dot');
const bubble = document.getElementById('bubble');
const gear   = document.getElementById('gear');
const panel  = document.getElementById('panel');

// 设置项
const muteChk     = document.getElementById('muteChk');
const prob        = document.getElementById('prob');
const voice       = document.getElementById('voice');
const autoTuneChk = document.getElementById('autoTuneChk');
const diaryChk    = document.getElementById('diaryChk');
const monoChk     = document.getElementById('monoChk');
const runMode     = document.getElementById('runMode');
const maxDays     = document.getElementById('maxDays');
const privacyMode = document.getElementById('privacyMode');
const hideBubble  = document.getElementById('hideBubble');

const ttsMode        = document.getElementById('ttsMode');
const ttsLocalUrl    = document.getElementById('ttsLocalUrl');
const ttsTimeout     = document.getElementById('ttsTimeout');
const localDeviceSel = document.getElementById('localDeviceSel');
const speakerSel     = document.getElementById('speakerSel');

const llmSource  = document.getElementById('llmSource');
const sizePreset = document.getElementById('sizePreset');
const saveBtn    = document.getElementById('saveBtn');

// ====== 全局配置（与 /config 对齐）======
let GLOBAL_CFG = {
  mute:false, prefer_cache_prob:0.6, voice_override:null, auto_tune_cache:false,
  diary_enabled:false, monologue_enabled:false, run_mode:'standard', diary_max_days:60,
  privacy_mode:false, ui_hide_bubble:false,
  tts_mode:'auto', tts_local_url:'', tts_timeout_ms:8000,
  llm_mode:'auto', llm_local_url_small:'http://127.0.0.1:9970', llm_local_url_big:'http://127.0.0.1:9971',
  llm_small_chars_max:120, llm_big_chars_min:160,
  window_size_preset:'medium',
  window_position:null
};

let BUSY = false;

// ====== 工具 ======
function joinUrl(base, path){
  if (!path) return base;
  if (/^https?:\/\//.test(path)) return path;
  if (path.startsWith('/')) return base + path;
  return base + '/' + path;
}

function show(text, ms = 2500, force = false){
  if (!bubble) return;
  const shouldHide = GLOBAL_CFG.ui_hide_bubble && !force;
  if (shouldHide){ bubble.style.display='none'; return; }
  bubble.style.display = '';
  bubble.textContent = text || '';
  bubble.classList.add('show');
  if (show._t) clearTimeout(show._t);
  show._t = setTimeout(() => { bubble.classList.remove('show'); bubble.textContent=''; }, ms);
}

function playAudio(url){
  if (GLOBAL_CFG.mute) return;
  try{ new Audio(url).play().catch(()=>{}); }catch{}
}

// ====== 健康检查 ======
async function healthCheck(maxRetries = 10, interval = 800){
  for (let i=1; i<=maxRetries; i++){
    try{
      // /ready
      {
        const c = new AbortController(); const t = setTimeout(()=>c.abort(), 2000);
        try{
          const rd = await fetch(joinUrl(API,'/ready'), { signal:c.signal });
          if (rd.ok){
            const data = await rd.json();
            if (data && data.ready) return true;
            show(`后端预热中 (${i}/${maxRetries})`, interval, true);
          }
        } finally { clearTimeout(t); }
      }
      // /ping
      {
        const c = new AbortController(); const t = setTimeout(()=>c.abort(), 2000);
        const p = await fetch(joinUrl(API,'/ping'), { signal:c.signal });
        clearTimeout(t);
        if (p.ok) return true;
      }
    }catch(e){
      console.log(`[Luna] health attempt ${i}/${maxRetries} err:`, e.message || e);
    }
    if (i<maxRetries) await new Promise(r=>setTimeout(r, interval));
  }
  return false;
}

// ====== 读取配置 & 刷 UI ======
async function loadConfig(){
  try{
    const r = await fetch(joinUrl(API, '/config'));
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    GLOBAL_CFG = await r.json();

    if (muteChk)      muteChk.checked = !!GLOBAL_CFG.mute;
    if (prob)         prob.value      = GLOBAL_CFG.prefer_cache_prob ?? 0.6;
    if (voice)        voice.value     = GLOBAL_CFG.voice_override || '';
    if (autoTuneChk)  autoTuneChk.checked = !!GLOBAL_CFG.auto_tune_cache;

    if (diaryChk)     diaryChk.checked = !!GLOBAL_CFG.diary_enabled;
    if (monoChk)      monoChk.checked  = !!GLOBAL_CFG.monologue_enabled;
    if (runMode)      runMode.value    = GLOBAL_CFG.run_mode || 'standard';
    if (maxDays)      maxDays.value    = GLOBAL_CFG.diary_max_days ?? 60;
    if (privacyMode)  privacyMode.checked = !!GLOBAL_CFG.privacy_mode;
    if (hideBubble)   hideBubble.checked  = !!GLOBAL_CFG.ui_hide_bubble;

    if (ttsMode)      ttsMode.value    = GLOBAL_CFG.tts_mode || 'auto';
    if (ttsLocalUrl)  ttsLocalUrl.value= GLOBAL_CFG.tts_local_url || '';
    if (ttsTimeout)   ttsTimeout.value = GLOBAL_CFG.tts_timeout_ms ?? 8000;

    if (localDeviceSel){
      const u = (GLOBAL_CFG.tts_local_url || '').trim();
      localDeviceSel.value = /9882$/.test(u) ? 'gpu' : /9883$/.test(u) ? 'cpu' : 'auto';
    }

    if (speakerSel){
      speakerSel.innerHTML = '<option value="">（不选）</option>';
      const base = (GLOBAL_CFG.tts_local_url || '').trim();
      if (base){
        try{
          const r2 = await fetch(joinUrl(base, '/speakers'));
          if (r2.ok){
            const data = await r2.json();
            const list = Array.isArray(data) ? data : (data.speakers || []);
            speakerSel.innerHTML = '<option value="">（不选）</option>' +
              list.map(s => `<option value="${s}">${s}</option>`).join('');
            if (GLOBAL_CFG.voice_override){
              speakerSel.value = GLOBAL_CFG.voice_override;
            }
          }
        }catch(e){ console.warn('[Luna] load speakers fail:', e); }
      }
    }

    if (llmSource){
      const mode = (GLOBAL_CFG.llm_mode || 'cloud').toLowerCase();
      let v = 'cloud';
      if (mode === 'local_small') v = 'local_small';
      else if (mode === 'local_big') v = 'local_big';
      else if (mode === 'local_only' || mode === 'auto') v = 'local_auto';
      llmSource.value = v;
    }

    if (sizePreset){
      sizePreset.value = (GLOBAL_CFG.window_size_preset || 'medium');
    }

    // ✅ 驱动 CSS 变量（球/齿轮/面板字号等随预设变化）
    document.body.dataset.size = (GLOBAL_CFG.window_size_preset || 'medium');

  }catch(e){
    console.warn('[Luna] load config fail:', e);
  }
  if (bubble) bubble.style.display = (GLOBAL_CFG.ui_hide_bubble ? 'none' : '');
}

// ====== 保存配置 ======
async function saveConfig(){
  try{
    const chosenSpeaker = (speakerSel && speakerSel.value) ? speakerSel.value :
                          (voice && voice.value ? voice.value : null);

    const payload = {
      mute: !!(muteChk && muteChk.checked),
      prefer_cache_prob: Math.max(0, Math.min(1, parseFloat((prob && prob.value) || '0.6'))),
      voice_override: chosenSpeaker,
      auto_tune_cache: !!(autoTuneChk && autoTuneChk.checked),

      diary_enabled:     !!(diaryChk && diaryChk.checked),
      monologue_enabled: !!(monoChk  && monoChk.checked),
      run_mode: (runMode && runMode.value) || 'standard',
      diary_max_days: parseInt((maxDays && maxDays.value) || '60', 10),

      privacy_mode: !!(privacyMode && privacyMode.checked),
      ui_hide_bubble: !!(hideBubble && hideBubble.checked),

      tts_mode: (ttsMode && ttsMode.value) || 'auto',
      tts_local_url: (ttsLocalUrl && ttsLocalUrl.value || '').trim(),
      tts_timeout_ms: parseInt((ttsTimeout && ttsTimeout.value) || '8000', 10),

      window_size_preset: (sizePreset && sizePreset.value) || 'medium'
    };

    if (localDeviceSel){
      const choice = localDeviceSel.value;
      if (choice === 'gpu') payload.tts_local_url = 'http://127.0.0.1:9882';
      else if (choice === 'cpu') payload.tts_local_url = 'http://127.0.0.1:9883';
    }

    const r = await fetch(joinUrl(API, '/config'), {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const resp = await r.json();
    GLOBAL_CFG = resp.config || resp || payload;

    if (ttsLocalUrl) ttsLocalUrl.value = GLOBAL_CFG.tts_local_url || '';
    if (localDeviceSel){
      const u = (GLOBAL_CFG.tts_local_url || '').trim();
      localDeviceSel.value = /9882$/.test(u) ? 'gpu' : /9883$/.test(u) ? 'cpu' : 'auto';
    }
    if (panel) panel.hidden = true;
    show('✓ 设置已保存', 1500, true);
    if (bubble) bubble.style.display = (GLOBAL_CFG.ui_hide_bubble ? 'none' : '');
  }catch(e){
    console.warn('[Luna] save config fail:', e);
    show('✗ 保存失败', 1500, true);
  }
}

// ====== LLM 来源切换 ======
async function setLLMMode(uiValue) {
  let body = {};
  if (uiValue === 'cloud') body = { llm_mode: 'cloud' };
  else if (uiValue === 'local_small') body = { llm_mode: 'local_small', llm_local_url_small: 'http://127.0.0.1:9970' };
  else if (uiValue === 'local_big')   body = { llm_mode: 'local_big',   llm_local_url_big:   'http://127.0.0.1:9971' };
  else if (uiValue === 'local_auto')  body = {
    llm_mode: 'local_only',
    llm_local_url_small: 'http://127.0.0.1:9970',
    llm_local_url_big:   'http://127.0.0.1:9971',
    llm_small_chars_max: 120,
    llm_big_chars_min:   160
  };
  try {
    const r = await fetch(joinUrl(API, '/config'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const cfg = await r.json();
    GLOBAL_CFG = cfg.config || GLOBAL_CFG;
    show('✓ LLM 来源已切换', 1200, true);
  } catch (err) {
    console.error('[LLM] set config failed:', err);
    alert('设置 LLM 来源失败，请检查后端服务或本地端口 9970/9971');
  }
}

// ====== 触发一次事件 ======
async function fire(evType='poke'){
  if (BUSY){ show('请稍等…', 600, true); return; }
  BUSY = true;
  show('思考中…', 1000, true);
  if (dot){
    dot.classList.remove('pulse','breathe');
    const lightning = dot.querySelector('.lightning');
    if (lightning) lightning.remove();
  }
  try{
    const r = await fetch(joinUrl(API, '/event'), {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ type: evType, timestamp: Date.now() })
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const { text, audio_url, branch, dt, meta } = data || {};

    if (meta && typeof meta.is_night === 'boolean'){
      document.body.classList.toggle('night-mode', meta.is_night);
    }
    show(text || '我在。', 5000);

    if (dot && branch){
      if (branch === 'online'){
        dot.classList.add('pulse');
        const lightning = document.createElement('div');
        lightning.className = 'lightning';
        dot.appendChild(lightning);
        setTimeout(()=>{ dot.classList.remove('pulse'); lightning.remove(); }, 1200);
        if (bubble){ bubble.classList.add('glitch'); setTimeout(()=>bubble.classList.remove('glitch'), 600); }
      } else if (branch === 'cache'){
        dot.classList.add('breathe'); setTimeout(()=>dot.classList.remove('breathe'), 1500);
      }
    }
    if (audio_url) playAudio(joinUrl(API, audio_url));
  }catch(e){
    console.error('[Luna] /event error:', e);
    show('连接失败，请检查后端服务', 3000, true);
  }finally{
    BUSY = false;
  }
}

// ====== 交互绑定 ======
if (dot)   dot.addEventListener('click', () => fire('poke'));
if (gear)  gear.addEventListener('click', async () => {
  if (!panel) return;
  panel.hidden = !panel.hidden;
  if (!panel.hidden){
    await loadConfig();
    panel.classList.remove('flip','bottom');
    requestAnimationFrame(() => {
      const margin = 8;
      const r = panel.getBoundingClientRect();
      if (r.right  > window.innerWidth  - margin) panel.classList.add('flip');
      if (r.bottom > window.innerHeight - margin) panel.classList.add('bottom');
      panel.style.maxHeight = `calc(100vh - ${margin*2 + 64}px)`;
    });
  }
});
if (saveBtn) saveBtn.addEventListener('click', saveConfig);
if (llmSource) llmSource.addEventListener('change', e => setLLMMode(e.target.value));

// ✅ 监听主进程的“窗口移动事件”→ 写入 /config
if (window.Luna && typeof window.Luna.onWindowMoved === 'function'){
  window.Luna.onWindowMoved(async (pos) => {
    try{
      await fetch(joinUrl(API, '/config'), {
        method: 'POST',
        headers: { 'Content-Type':'application/json' },
        body: JSON.stringify({ window_position: { x: pos.x|0, y: pos.y|0 } })
      });
    }catch(e){ /* 忽略 */ }
  });
}

// ✅ 大小预设切换：主进程 setSize + /config 持久化 + CSS 变量同步
if (sizePreset){
  sizePreset.addEventListener('change', async (e) => {
    const v = e.target.value || 'medium';
    try { await (window.Luna && window.Luna.setSizePreset ? window.Luna.setSizePreset(v) : null); } catch {}
    try{
      await fetch(joinUrl(API, '/config'), {
        method: 'POST',
        headers: { 'Content-Type':'application/json' },
        body: JSON.stringify({ window_size_preset: v })
      });
      document.body.dataset.size = v;   // 立刻驱动视觉变化
      show('✓ 尺寸已切换', 900, true);
    }catch(e){ /* 忽略 */ }
  });
}

// ====== 启动 ======
(async function boot(){
  show('正在连接后端，请稍候…', 2000);
  const ok = await healthCheck(10, 800);
  if (ok){
    show('系统就绪，点击交互 ✨', 1600);
    await loadConfig();
    const hour = new Date().getHours();
    document.body.classList.toggle('night-mode', (hour >= 22) || (hour <= 6));
  }else{
    show('⚠️ 后端服务未响应，请检查启动状态', 0, true);
  }
})();
