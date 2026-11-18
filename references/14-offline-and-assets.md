# 14 · 离线运行与素材自给

> 目标：交付一个**断网也能打开**、**不依赖任何外部图片/模型**的 3D 页面。
> 本文给出三种运行模式的完整模板、程序化素材生成方案、以及体积取舍判断。

---

## 一、三种运行模式

### 模式 A：standalone（推荐用于交付）

单文件、内联 three 运行时、双击即开、断网可用。**file:// 协议下唯一 100% 可靠的方式**
（ES module 在 file:// 下会被 CORS 拦截）。

```bash
python3 scripts/forge_init.py ./out --title "行星齿轮减速器" --mode standalone
```

生成结构：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <title>...</title>
  <style>/* 全部内联 */</style>
</head>
<body>
  <canvas id="stage"></canvas>
  <div id="fallback" hidden>当前环境不支持 WebGL</div>

  <script>/* three.bundle.min.js 全文内联，1.3MB */</script>
  <script>
    const { THREE, OrbitControls, RoomEnvironment, EffectComposer,
            RenderPass, UnrealBloomPass, OutputPass } = window.THREE_BUNDLE;
    // ... 场景代码
  </script>
</body>
</html>
```

**要点**
- 不要写 `type="module"`，不要留 `importmap`
- bundle 已含 43 个常用 addon，直接解构，不要再 import
- 体积约 1.3–1.5MB，gzip 后约 350KB（如果服务器开了压缩）

### 模式 B：cdn（单文件、轻、需联网）

```html
<script type="importmap">
{
  "imports": {
    "three": "https://fastly.jsdelivr.net/npm/three@0.187.0/build/three.module.js",
    "three/addons/": "https://fastly.jsdelivr.net/npm/three@0.187.0/examples/jsm/"
  }
}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
</script>
```

**要点**
- 版本必须锁死 `0.187.0`，不能写 `latest` 或 `^0.187.0`
- 禁用 unpkg / bootcdn / staticfile（供应链风险，`validate_scene.py` 的 E04）
- 打开页面需要联网；断网白屏

### 模式 C：local（离线 + 可读源码）

```html
<script type="importmap">
{
  "imports": {
    "three": "./three/build/three.module.js",
    "three/addons/": "./three/addons/"
  }
}
</script>
```

目录：

```
project/
├── index.html
└── three/
    ├── build/
    │   ├── three.module.js
    │   └── three.core.js      ← 必须有，r187 拆分架构
    └── addons/
        └── controls/OrbitControls.js
```

**要点**
- 需要 HTTP 服务（`python3 -m http.server`），file:// 下 module 会被拦
- `three.core.js` 缺失会 404 白屏（E14 专查）
- 适合需要替换 addon 或读源码调试的场景

### 模式选择决策

```
需要发给别人双击就开？ ──是──→ standalone
        │否
需要断网演示？ ──是──→ standalone 或 local
        │否
只是自己看/快速迭代？ ──是──→ cdn
        │
需要改 addon 源码？ ──是──→ local
```

---

## 二、程序化素材（不下载任何图片）

专业感的 90% 来自**材质细节**，而细节不必来自贴图文件。以下方案全部在运行时生成。

### 1. 值噪声纹理（做粗糙度/凹凸/污渍）

```js
function makeNoiseTexture(size = 512, seed = 1) {
  // 确定性伪随机，保证每次生成一致
  let s = seed;
  const rand = () => (s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296;

  // 低频格点
  const grid = 32;
  const lattice = Array.from({ length: grid * grid }, rand);
  const at = (x, y) => lattice[(y % grid) * grid + (x % grid)];

  const smooth = t => t * t * (3 - 2 * t);
  const lerp = (a, b, t) => a + (b - a) * t;

  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const img = ctx.createImageData(size, size);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const fx = (x / size) * grid, fy = (y / size) * grid;
      const x0 = Math.floor(fx), y0 = Math.floor(fy);
      const tx = smooth(fx - x0), ty = smooth(fy - y0);
      const v = lerp(
        lerp(at(x0, y0), at(x0 + 1, y0), tx),
        lerp(at(x0, y0 + 1), at(x0 + 1, y0 + 1), tx),
        ty
      );
      const i = (y * size + x) * 4;
      const g = Math.round(v * 255);
      img.data[i] = img.data[i + 1] = img.data[i + 2] = g;
      img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);

  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.NoColorSpace;   // 数据贴图必须线性
  tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return tex;
}

// 用法：粗糙度微扰
const noise = makeNoiseTexture(512, 7);
noise.repeat.set(4, 4);
mat.roughnessMap = noise;
mat.roughness = 0.55;      // 与贴图相乘，贴图提供变化，标量提供基准
```

### 2. 拉丝金属（anisotropy 各向异性）

```js
function makeBrushedTexture(size = 512) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#808080';
  ctx.fillRect(0, 0, size, size);
  for (let i = 0; i < size * 2; i++) {
    const y = Math.random() * size;
    const g = 100 + Math.random() * 90;
    ctx.strokeStyle = `rgba(${g},${g},${g},0.35)`;
    ctx.lineWidth = Math.random() * 1.6;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(size, y + (Math.random() - 0.5) * 2);
    ctx.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.NoColorSpace;
  return t;
}
```

### 3. 划痕与污渍（叠加到 roughness）

```js
function addScratches(ctx, size, count = 60) {
  ctx.globalCompositeOperation = 'lighter';
  for (let i = 0; i < count; i++) {
    const x = Math.random() * size, y = Math.random() * size;
    const len = 20 + Math.random() * 120;
    const ang = Math.random() * Math.PI * 2;
    ctx.strokeStyle = `rgba(255,255,255,${0.08 + Math.random() * 0.18})`;
    ctx.lineWidth = 0.4 + Math.random() * 1.2;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + Math.cos(ang) * len, y + Math.sin(ang) * len);
    ctx.stroke();
  }
  ctx.globalCompositeOperation = 'source-over';
}
```

### 4. 环境贴图（不下载 HDR）

```js
// 首选：程序化室内环境，产品展示的标准做法
const pmrem = new THREE.PMREMGenerator(renderer);
pmrem.compileEquirectangularShader();
const envRT = pmrem.fromScene(new RoomEnvironment(), 0.04);
scene.environment = envRT.texture;

// 备选：自定义渐变环境（品牌色打光）
function makeGradientEnv() {
  const c = document.createElement('canvas');
  c.width = 64; c.height = 256;
  const ctx = c.getContext('2d');
  const g = ctx.createLinearGradient(0, 0, 0, 256);
  g.addColorStop(0.0, '#ffffff');   // 顶光
  g.addColorStop(0.45, '#c8d4e8');  // 天光
  g.addColorStop(0.55, '#8a8f98');  // 地平线
  g.addColorStop(1.0, '#20242c');   // 地面反弹
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 256);
  const tex = new THREE.CanvasTexture(c);
  tex.mapping = THREE.EquirectangularReflectionMapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  return pmrem.fromEquirectangular(tex).texture;
}
```

### 5. 文字（不加载字体文件）

`TextGeometry` 需要 `typeface.json`（中文字体动辄几 MB）。**用 Canvas 纹理代替**：

```js
function makeLabel(text, { w = 512, h = 128, color = '#fff', bg = null } = {}) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d');
  if (bg) { ctx.fillStyle = bg; ctx.fillRect(0, 0, w, h); }
  ctx.fillStyle = color;
  ctx.font = `600 ${Math.round(h * 0.52)}px -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, w / 2, h / 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return tex;
}

// 贴在平面或 sprite 上
const label = new THREE.Mesh(
  new THREE.PlaneGeometry(1.2, 0.3),
  new THREE.MeshBasicMaterial({ map: makeLabel('额定扭矩 120 N·m'), transparent: true })
);
```

### 6. 模型（不加载外部 glb）

用内置几何组合 + `ExtrudeGeometry` 做型材，足以覆盖机械/建筑/抽象类主体：

```js
// 齿轮：轮廓 + 拉伸
function makeGearShape(teeth = 18, rOuter = 1, rInner = 0.82, hole = 0.25) {
  const shape = new THREE.Shape();
  const step = (Math.PI * 2) / teeth;
  for (let i = 0; i < teeth; i++) {
    const a = i * step;
    const pts = [
      [rInner, a],
      [rOuter, a + step * 0.28],
      [rOuter, a + step * 0.52],
      [rInner, a + step * 0.8],
    ];
    pts.forEach(([r, ang], j) => {
      const x = Math.cos(ang) * r, y = Math.sin(ang) * r;
      (i === 0 && j === 0) ? shape.moveTo(x, y) : shape.lineTo(x, y);
    });
  }
  shape.closePath();
  const h = new THREE.Path();
  h.absarc(0, 0, hole, 0, Math.PI * 2, true);
  shape.holes.push(h);
  return shape;
}

const gear = new THREE.Mesh(
  new THREE.ExtrudeGeometry(makeGearShape(), {
    depth: 0.18, bevelEnabled: true, bevelSize: 0.008, bevelThickness: 0.008, bevelSegments: 2
  }),
  new THREE.MeshStandardMaterial({ color: 0x9aa3ad, metalness: 1, roughness: 0.32 })
);
```

---

## 三、体积与性能取舍

| 素材 | 方案 | 体积 | 质量 |
|---|---|---|---|
| 环境光照 | `RoomEnvironment` 程序化 | 0 | 高 |
| 环境光照 | HDR 2K | 2–6MB | 极高 |
| 纹理 | Canvas 程序化 512² | 0（内存 ~1MB） | 中高 |
| 纹理 | WebP 1024² | 100–300KB | 高 |
| 模型 | 参数化几何 | 0 | 中（适合机械/建筑） |
| 模型 | glTF 内联 base64 | 原体积 ×1.37 | 极高 |
| 文字 | Canvas 纹理 | 0 | 够用 |
| 文字 | TextGeometry + 字体 | 1–10MB（中文） | 高 |

**默认策略**：全部程序化。只有当主体是"无法参数化的有机形态"（人物、动物、真实产品外壳）
才引入模型文件，并优先 glTF + Draco。

---

## 四、离线验收清单

```
[ ] 断网打开，页面正常渲染（不是黑屏/白屏）
[ ] file:// 直接双击打开（standalone）或 http 服务打开（local/cdn）
[ ] 控制台无 404、无 CORS 报错
[ ] 无任何 http(s) 外部请求（DevTools → Network 全空）
[ ] 首次渲染 < 3s（本地）
[ ] 静止时 GPU 占用回落（demand 模式）
[ ] 窗口缩放不变形，像素比不超 2
[ ] 切到后台再切回，动画不跳变
[ ] 弱设备（关掉硬件加速）显示兜底文案而不是白屏
```
