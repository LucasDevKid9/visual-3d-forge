# 11 · three.js r0.187.0 · API 权威字典

> 本文件所有事实均来自包内 `build/` 与 `examples/jsm/` 源码实测，不是记忆。
> 写代码时以本文件为准；本文件没有的 API，先查 `assets/three/build/` 再写，不要凭印象补。

---

## 一、架构事实（决定引入方式，写错必白屏）

### 1. 构建产物是拆分的

```
build/
├── three.module.js      644KB   ESM 入口，首行 import { ... } from './three.core.js'
├── three.core.js        1.5MB   真正的实现体
├── three.webgpu.js      1.3MB   WebGPU 入口（含 TSL 运行时）
├── three.webgpu.nodes.js 2.3MB  WebGPU + NodeMaterial
├── three.tsl.js         1.1MB   TSL 独立入口
└── three.cjs            631B    CJS 转发层
```

**关键约束：`three.module.js` 与 `three.core.js` 必须同目录。**

r187 把实现体拆到 core，module 只是转发层。任何"只拷 three.module.js"的离线方案都会 404。
这是 v1 最容易踩的坑，`validate_scene.py` 的 **E14** 专门检查这一点。

### 2. package.json exports

```json
{
  ".": { "import": "./build/three.module.js" },
  "./examples/jsm/*": "./examples/jsm/*",
  "./addons": "./examples/jsm/Addons.js",
  "./addons/*": "./examples/jsm/*",
  "./webgpu": "./build/three.webgpu.js",
  "./tsl": "./build/three.tsl.js",
  "./src/*": "./src/*"
}
```

### 3. 三种可用引入方式

| 模式 | importmap | 优点 | 代价 |
|---|---|---|---|
| **standalone** | 无（内联 IIFE bundle） | 离线、双击即开、file:// 不被 CORS 拦 | 1.3MB 体积 |
| **cdn** | jsDelivr + `three@0.187.0` | 单文件、体积小 | 必须联网 |
| **local** | 相对路径 `./three/build/` | 离线、可读源码 | 需带资源目录 |

standalone 用 `scripts/build_standalone.py` 生成；local 用 `forge_init.py --mode local`。
**三种模式不要混用**：同时存在 `THREE_BUNDLE` 和 `importmap` 会加载两份 three 实例，
导致 `instanceof` 判断失效（这是最难查的 bug 之一）。

### 4. 导出规模

- `three.module.js` 导出 443 个符号，`three.core.js` 448 个，去重后 **438 个大写开头类/常量**
- `examples/jsm` 共 **506 个 addon 文件**

---

## 二、r187 必须知道的变更

| 已移除 / 已废弃 | 替代 | 移除版本 |
|---|---|---|
| `renderer.outputEncoding` | `renderer.outputColorSpace = THREE.SRGBColorSpace` | r152 |
| `THREE.sRGBEncoding` | `THREE.SRGBColorSpace` | r152 |
| `renderer.physicallyCorrectLights` | 物理光照已成默认，删掉即可 | r155 |
| `renderer.useLegacyLights` | 同上 | r165 |
| `THREE.Geometry` / `THREE.Face3` | `BufferGeometry` + index | r125 |
| `renderer.gammaOutput` / `gammaFactor` | `outputColorSpace` / `toneMappingExposure` | r112 |

**新增能力（r187 可用）**：

- `THREE.AgXToneMapping`、`THREE.NeutralToneMapping` — 电影级 / 中性色调映射，优于 ACES 的偏色问题
- `THREE.Timer` — 替代 `Clock`，支持 `connect(document)` 自动处理页面可见性
- `THREE.BatchedMesh` — 多材质合批，比 InstancedMesh 更灵活
- `THREE.WebGPURenderer` — WebGPU 后端，API 与 WebGLRenderer 基本一致

---

## 三、色彩管线（唯一正确写法）

```js
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });

// ① 输出色彩空间：只设一次
renderer.outputColorSpace = THREE.SRGBColorSpace;   // 默认已是此值，显式写是为了自文档化

// ② 色调映射：只设一次
renderer.toneMapping = THREE.ACESFilmicToneMapping; // 或 AgX / Neutral
renderer.toneMappingExposure = 1.0;                 // 0.8–1.2 之间调

// ③ 像素比：必须封顶
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

// ④ 阴影
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;   // VSMShadowMap 更柔但需调 radius
```

**双次转换的症状**：画面发灰、暗部浮起、高光不透。原因通常是既设了 `outputColorSpace`
又在后处理里做了 gamma 转换。检查 `validate_scene.py` 的 E06 / E07。

**贴图色彩空间**：颜色贴图必须标 sRGB，数据贴图必须保持线性。

```js
colorTex.colorSpace = THREE.SRGBColorSpace;      // map / emissiveMap / envMap
dataTex.colorSpace = THREE.NoColorSpace;         // normal / roughness / metalness / ao / displacement
```

---

## 四、核心 API 速查

### 渲染器

```js
new THREE.WebGLRenderer({ antialias, alpha, powerPreference, preserveDrawingBuffer })
renderer.setSize(w, h, false)        // false = 不写 style，由 CSS 控制
renderer.setAnimationLoop(fn)        // 优于 rAF：WebXR 必需，且便于统一暂停
renderer.render(scene, camera)
renderer.info.render.calls           // 绘制调用数，性能诊断第一指标
renderer.info.render.triangles
renderer.dispose()
```

### 场景 / 相机

```js
new THREE.Scene()
scene.background = new THREE.Color(0x0a0a0c)   // 或 Texture
scene.environment = envTexture                  // IBL，影响所有 PBR 材质
scene.fog = new THREE.Fog(color, near, far)

new THREE.PerspectiveCamera(fov, aspect, near, far)   // fov 32–45，near ≥ 0.01
new THREE.OrthographicCamera(left, right, top, bottom, near, far)
camera.updateProjectionMatrix()                 // 改 fov/aspect/near/far 后必须调
```

**相机限位由包围球推导**，不要写死：

```js
const box = new THREE.Box3().setFromObject(subject);
const sphere = box.getBoundingSphere(new THREE.Sphere());
const dist = sphere.radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.25;
controls.minDistance = dist * 0.6;
controls.maxDistance = dist * 2.2;
```

### 几何（内置，无需 addon）

`BoxGeometry` `SphereGeometry` `PlaneGeometry` `CylinderGeometry` `ConeGeometry`
`TorusGeometry` `TorusKnotGeometry` `CapsuleGeometry` `LatheGeometry` `ExtrudeGeometry`
`ShapeGeometry` `TubeGeometry` `RingGeometry` `CircleGeometry` `IcosahedronGeometry`
`OctahedronGeometry` `DodecahedronGeometry` `TetrahedronGeometry` `EdgesGeometry`
`WireframeGeometry` `BufferGeometry`

**参数化建模优先于堆盒子**：`LatheGeometry` 做回转体（瓶、碗、轴），`ExtrudeGeometry`
做型材（齿轮、法兰、导轨），`TubeGeometry` 做管路/线缆，`Shape` + holes 做开孔板。

### 材质

```js
new THREE.MeshStandardMaterial({ color, roughness, metalness, flatShading })
new THREE.MeshPhysicalMaterial({ ..., clearcoat, clearcoatRoughness, transmission, thickness, ior, sheen })
new THREE.MeshBasicMaterial({ color, map, transparent, opacity })
new THREE.MeshNormalMaterial()
new THREE.LineBasicMaterial({ color })
new THREE.PointsMaterial({ size, sizeAttenuation, map, transparent })
new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader })
```

**物理正确性铁律**：
- `metalness` 是二元的：纯金属 1.0，非金属 0.0。0.5 只应出现在真实混合界面（如镀层磨损）
- `roughness` 0.0 = 镜面，1.0 = 完全漫反射。产品渲染常用 0.25–0.65
- 非金属不要用 `metalness > 0` 来"提亮"，那会让材质变成假金属
- `transmission` 需要 `transparent: true` 且渲染成本高，玻璃件控制在 1–2 个

### 光照（三光制）

```js
// 主光：定形，产生主要阴影
const key = new THREE.DirectionalLight(0xffffff, 2.2);
key.position.set(4, 6, 3);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.bias = -0.0005;        // 治 shadow acne
key.shadow.normalBias = 0.02;     // 治 peter-panning

// 补光：抬暗部，不产生阴影
const fill = new THREE.DirectionalLight(0xbcd4ff, 0.6);
fill.position.set(-5, 2, 2);

// 轮廓光：勾边，从背后打
const rim = new THREE.DirectionalLight(0xffffff, 1.2);
rim.position.set(-2, 3, -6);

// 环境：IBL 兜底，避免纯黑
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
```

`RoomEnvironment` 在 r187 中**无参构造**（旧版需要传 renderer，写错会报错）。

### 动画与时间

```js
const timer = new THREE.Timer();
timer.connect(document);          // 自动处理 visibilitychange，切后台不累积

renderer.setAnimationLoop((t) => {
  timer.update(t);
  const dt = Math.min(timer.getDelta(), 0.05);   // 双保险
  const el = timer.getElapsed();
  // ... 用 dt 做速度积分，用 el 做周期动画
  renderer.render(scene, camera);
});
```

**用 `dt` 而不是固定步长**，否则高刷屏动画快一倍。
**用 `el` 做周期动画**（`Math.sin(el * 2)`），不受帧率影响。

### 交互

```js
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function onPointerMove(e) {
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
}

raycaster.setFromCamera(pointer, camera);
const hits = raycaster.intersectObjects(pickables, false);
```

**拾取优化**：只对 `pickables` 数组求交，不要 `intersectObjects(scene.children, true)`。

---

## 五、幻觉 API 黑名单

以下写法看起来合理但**不存在**，写出即报错：

| 幻觉写法 | 实际 |
|---|---|
| `new THREE.EnvironmentTextureLoader()` | 用 `RGBELoader` / `GLTFLoader` / `CubeTextureLoader` |
| `THREE.MeshStandardMaterial.specular` | Standard 无 specular，用 Physical 或调 roughness |
| `renderer.setClearAlpha(color)` | `renderer.setClearColor(color, alpha)` |
| `scene.addLight()` | `scene.add(light)` |
| `geometry.dispose()` 后继续用 | dispose 后必须重建 |
| `material.color.setHex('#fff')` | `setHex(0xffffff)` 或 `setStyle('#ffffff')` |
| `camera.lookAt(x, y, z)` 后忘记 `updateProjectionMatrix` | lookAt 不需要，改 fov/aspect 才需要 |
| `light.intensity` 用旧版 0–1 范围 | r155 起物理单位，DirectionalLight 常用 1–4 |
| `THREE.sRGBEncoding` | `THREE.SRGBColorSpace` |
| `new THREE.Geometry()` | `new THREE.BufferGeometry()` |

---

## 六、性能 API

```js
// 实例化：同几何同材质，几十个以上必须用
const inst = new THREE.InstancedMesh(geo, mat, count);
const m = new THREE.Matrix4();
for (let i = 0; i < count; i++) {
  m.compose(pos, quat, scale);
  inst.setMatrixAt(i, m);
}
inst.instanceMatrix.needsUpdate = true;
inst.castShadow = true;

// 合批：不同几何但同材质
const merged = BufferGeometryUtils.mergeGeometries([g1, g2, g3], false);

// 释放：卸载场景时逐个释放
scene.traverse(o => {
  if (o.geometry) o.geometry.dispose();
  if (o.material) {
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    mats.forEach(m => {
      Object.values(m).forEach(v => { if (v && v.isTexture) v.dispose(); });
      m.dispose();
    });
  }
});
```

**性能预算（桌面 / 移动）**

| 指标 | 桌面 | 移动 |
|---|---|---|
| 绘制调用 | < 150 | < 60 |
| 三角面 | < 500k | < 150k |
| 像素比 | ≤ 2 | ≤ 1.5 |
| 阴影贴图 | 2048 | 1024 |
| 后处理 | bloom 可开 | 建议关 |

---

## 七、WebGL 能力检测与兜底

```js
function hasWebGL() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGLRenderingContext &&
      (c.getContext('webgl2') || c.getContext('webgl')));
  } catch (e) { return false; }
}

if (!hasWebGL()) {
  document.getElementById('fallback').hidden = false;  // 静态图 + 文字说明
} else {
  boot();
}

canvas.addEventListener('webglcontextlost', e => {
  e.preventDefault();
  cancelAnimationFrame(rafId);
}, false);

canvas.addEventListener('webglcontextrestored', () => {
  init();  // 重建资源
}, false);
```
