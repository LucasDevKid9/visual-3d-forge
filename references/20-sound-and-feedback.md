# 20 · 声音与反馈（Sound & Feedback）

> **适用于体验型产物。确认件不加声音。**
> 理由不是保守：一份要被人拿去签字的工程文件，配了音效之后，评审会上第一个问题会变成「这个音乐能关吗」。
> 判定过程见 [`../guide/06-EXPERIENCE.md`](../guide/06-EXPERIENCE.md)。

> 单文件 HTML 不能带 mp3。**用 Web Audio 程序化合成，一行外部资源都不用。**
> 本文件给可直接粘贴的音频引擎。

---

## 一、声音的四个角色

| 角色 | 作用 | 例子 |
|---|---|---|
| **节拍器** Metronome | 给全站动效提供时间基准 | 174 BPM 的底鼓 |
| **状态音** State | 标记状态转移 | 进入 / 完成 / 失败 |
| **材质音** Material | 让物体"有质量" | 金属敲击、玻璃碎、布摩擦 |
| **氛围音** Ambience | 填满静默，避免"死寂" | 低频嗡鸣、风、电流 |

**配比**：氛围音常驻（音量最低），状态音事件驱动，材质音与交互绑定，节拍器只在需要时出现。

**禁止**：所有音同时出现。那是噪音，不是设计。

---

## 二、最小可用音频引擎（纯 Web Audio，无文件）

```js
// —— 音频总线：master → 三路分总线 ——
const AudioBus = (() => {
  let ctx = null, master, sfx, amb, music, ready = false, muted = false;

  function init() {
    if (ctx) return ctx;
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain(); master.gain.value = 0.0;
    master.connect(ctx.destination);

    sfx   = ctx.createGain(); sfx.gain.value   = 0.9; sfx.connect(master);
    amb   = ctx.createGain(); amb.gain.value   = 0.25; amb.connect(master);
    music = ctx.createGain(); music.gain.value = 0.5;  music.connect(master);
    ready = true;
    return ctx;
  }

  // 必须在用户手势内调用（浏览器自动播放策略）
  async function unlock() {
    init();
    if (ctx.state === 'suspended') await ctx.resume();
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.linearRampToValueAtTime(muted ? 0 : 0.8, ctx.currentTime + 0.4);
  }

  function setMuted(m) {
    muted = m;
    if (!ready) return;
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.linearRampToValueAtTime(m ? 0 : 0.8, ctx.currentTime + 0.2);
  }

  return {
    get ctx() { init(); return ctx; },
    get sfx() { init(); return sfx; },
    get amb() { init(); return amb; },
    get music() { init(); return music; },
    unlock, setMuted,
    get muted() { return muted; },
    get now() { init(); return ctx.currentTime; }
  };
})();
```

### 为什么分三路总线

- `master` 统一淡入淡出，避免"啪"的爆音
- `sfx` / `amb` / `music` 独立调平，不用改每个音源
- 静音只动 `master`，恢复时各音源状态不丢

---

## 三、五个必备音色（合成配方）

### 1. 点击 Click —— 短促、干脆

```js
function click(freq = 1800, dur = 0.03, gain = 0.25) {
  const ctx = AudioBus.ctx, t = ctx.currentTime;
  const osc = ctx.createOscillator(), g = ctx.createGain();
  osc.type = 'square';
  osc.frequency.setValueAtTime(freq, t);
  osc.frequency.exponentialRampToValueAtTime(freq * 0.55, t + dur);
  g.gain.setValueAtTime(gain, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.connect(g).connect(AudioBus.sfx);
  osc.start(t); osc.stop(t + dur + 0.01);
}
```

### 2. 确认 Confirm —— 上行两音

```js
function confirm(base = 523.25) {  // C5
  const ctx = AudioBus.ctx;
  [[base, 0], [base * 1.5, 0.075]].forEach(([f, d]) => {
    const t = ctx.currentTime + d;
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = 'sine'; o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.22, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.32);
    o.connect(g).connect(AudioBus.sfx);
    o.start(t); o.stop(t + 0.35);
  });
}
```

### 3. 转场 Whoosh —— 噪声扫频

```js
let _noiseBuf = null;
function noiseBuffer(ctx) {
  if (_noiseBuf) return _noiseBuf;
  const len = ctx.sampleRate * 2;
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  return (_noiseBuf = buf);
}

function whoosh(dur = 0.55, from = 200, to = 4000) {
  const ctx = AudioBus.ctx, t = ctx.currentTime;
  const src = ctx.createBufferSource(); src.buffer = noiseBuffer(ctx);
  const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 1.2;
  bp.frequency.setValueAtTime(from, t);
  bp.frequency.exponentialRampToValueAtTime(to, t + dur);
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(0.3, t + dur * 0.35);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  src.connect(bp).connect(g).connect(AudioBus.sfx);
  src.start(t); src.stop(t + dur + 0.02);
}
```

### 4. 冲击 Impact —— 低频下坠 + 噪声

```js
function impact(strength = 1) {
  const ctx = AudioBus.ctx, t = ctx.currentTime;
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = 'sine';
  o.frequency.setValueAtTime(120 * strength, t);
  o.frequency.exponentialRampToValueAtTime(28, t + 0.5);
  g.gain.setValueAtTime(0.5 * strength, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
  o.connect(g).connect(AudioBus.sfx);
  o.start(t); o.stop(t + 0.65);
  whoosh(0.25, 3000, 300);
}
```

### 5. 氛围 Ambient —— 常驻低频

```js
let _amb = null;
function startAmbient(freq = 55, vol = 0.12) {  // A1
  if (_amb) return;
  const ctx = AudioBus.ctx;
  const o1 = ctx.createOscillator(), o2 = ctx.createOscillator();
  o1.type = 'sine'; o1.frequency.value = freq;
  o2.type = 'sine'; o2.frequency.value = freq * 1.005; // 微失谐 = 呼吸感
  const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 400;
  const g = ctx.createGain(); g.gain.value = 0;
  g.gain.linearRampToValueAtTime(vol, ctx.currentTime + 2);
  o1.connect(lp); o2.connect(lp); lp.connect(g).connect(AudioBus.amb);
  o1.start(); o2.start();
  _amb = { o1, o2, g };
}
function stopAmbient() {
  if (!_amb) return;
  const t = AudioBus.ctx.currentTime;
  _amb.g.gain.linearRampToValueAtTime(0, t + 0.8);
  _amb.o1.stop(t + 0.9); _amb.o2.stop(t + 0.9);
  _amb = null;
}
```

### 材质音速查

| 材质 | 频率起点 | 波形 | 时长 | 附加 |
|---|---|---|---|---|
| 金属 | 2400 | `square` | 0.12 | 加短混响 |
| 玻璃 | 3200 | `sine` + 噪声 | 0.08 | 高频噪声爆 |
| 木头 | 800 | `triangle` | 0.10 | 低通 1200 |
| 布 / 纸 | — | 纯噪声 | 0.06 | 高通 2000 |
| 水 | 600 | `sine` 下滑 | 0.20 | 带通 800 |

---

## 四、节拍时钟：让画面和声音同源

**不要用 `setInterval` 打拍子**（漂移）。用音频时钟反推：

```js
function BeatClock(bpm = 174, onBeat = () => {}) {
  const beat = 60 / bpm;
  let startAt = 0, running = false, raf = 0;

  function loop() {
    if (!running) return;
    const t = AudioBus.ctx.currentTime - startAt;
    const idx = Math.floor(t / beat);
    if (idx !== loop._last) {
      loop._last = idx;
      onBeat(idx, idx % 4 === 0 ? 'bar' : 'beat');
    }
    raf = requestAnimationFrame(loop);
  }
  return {
    start() { startAt = AudioBus.ctx.currentTime; running = true; loop._last = -1; loop(); },
    stop() { running = false; cancelAnimationFrame(raf); },
    get phase() { return ((AudioBus.ctx.currentTime - startAt) % beat) / beat; },
    get beat() { return beat; }
  };
}
```

`phase` 用于"呼吸式"动画：`scale = 1 + 0.02 * Math.sin(phase * Math.PI * 2)`。

**关键**：所有时长用 `beat` 的整数倍，声音和画面自然同步，不需要手动对齐。

---

## 五、三通道反馈：视觉 / 听觉 / 触觉

任何一次有意义的交互，至少给两路反馈。

| 交互 | 视觉 | 听觉 | 触觉（移动端） |
|---|---|---|---|
| 悬停 | 缩放 1.02 + 光标变化 | 极轻 click（0.05 音量） | — |
| 点击 | 凹陷 0.96 → 回弹 | click | `navigator.vibrate(8)` |
| 成功 | 绿色描边 + 上浮 | confirm | `vibrate([10, 30, 10])` |
| 失败 | 红色抖动 3px | 下行两音 | `vibrate(60)` |
| 完成一幕 | 转场 + 计数 +1 | whoosh + confirm | `vibrate(15)` |

```js
const Haptic = {
  tap:  () => navigator.vibrate?.(8),
  ok:   () => navigator.vibrate?.([10, 30, 10]),
  fail: () => navigator.vibrate?.(60),
};
```

**触觉的硬约束**：只在移动端、只在用户已交互后、单次 ≤ 80ms。滥用会让用户关掉振动权限。

---

## 六、自动播放策略：必须遵守的三条

1. **AudioContext 必须在用户手势内创建或 resume**。否则 Chrome 会 `suspended`。
2. **进入页面时声音默认关闭**，显示 `SOUND ON / OFF`（样本 B 的做法）。
3. **首次点击时给一个"声音已开启"的确认音**，让用户知道生效了。

```js
let soundOn = false;
document.addEventListener('pointerdown', async function once() {
  document.removeEventListener('pointerdown', once);
  if (soundOn) { await AudioBus.unlock(); confirm(); }
}, { once: true });
```

---

## 七、降级：没有声音也要成立

| 情况 | 处理 |
|---|---|
| 用户关闭声音 | 所有"声音提示"必须有视觉等价物（描边、闪动、计数） |
| AudioContext 创建失败 | `try/catch` 包住 `init()`，失败后 `AudioBus` 所有方法变空操作 |
| 移动端静音键 | 无法检测，只能靠视觉兜底 |
| `prefers-reduced-motion` | 声音可保留，但取消与运动绑定的音效（如 whoosh） |

```js
// 安全包装：任何音频调用失败都不影响主流程
function safe(fn) { try { fn(); } catch (e) { /* 静默 */ } }
```

**硬要求**：整个体验在**全程静音**下仍能走完六段式，且每一步都有视觉反馈。做不到 = 声音被当成了拐杖。

---

## 八、声音设计的自检清单

- [ ] 进入页面**不自动出声**
- [ ] 有明确的 `SOUND ON/OFF` 控件，且状态可见
- [ ] 静音状态下所有交互仍有视觉反馈
- [ ] 全站音效数量 ≤ 8 种（多了记不住）
- [ ] 氛围音常驻但音量 ≤ 主音效的 1/3
- [ ] 没有用 `setInterval` 打拍子
- [ ] 幕退出时 `stopAmbient()` / 停掉该幕专属音源
- [ ] `AudioContext` 创建包在 `try/catch` 里
- [ ] 移动端触觉单次 ≤ 80ms
- [ ] 全静音走完一遍，六段式完整
