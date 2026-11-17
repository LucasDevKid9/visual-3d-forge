# 10 · 材质配方库

> 材质的真实感 90% 来自三个数：`metalness`、`roughness`、环境贴图。
> 剩下 10% 是 `clearcoat` / `transmission` / 法线细节。
> 本库给可直接抄的数值，不靠"感觉调一调"。

---

## 一、先理解三个参数

### metalness（金属度）

**它是二元属性，不是程度。** 现实中一种材料要么是金属，要么不是。

| 值 | 含义 | 典型 |
|---|---|---|
| 1.0 | 纯金属 | 铝、钢、铜、钛、铬 |
| 0.0 | 非金属 | 塑料、木头、玻璃、陶瓷、皮肤 |
| 0.5 | **几乎只出现在"金属漆/脏污金属"** | 车漆的金属颗粒层 |

写 `metalness: 0.5` 做"一般金属"是错的——那会得到一个既不像金属也不像塑料的灰色泥巴。

### roughness（粗糙度）

表面的微观起伏，决定反射是"镜面"还是"哑光"。

| 区间 | 观感 | 例 |
|---|---|---|
| 0.02–0.10 | 镜面 | 抛光铬、镜面玻璃 |
| 0.10–0.25 | 高光 | 抛光铝、车漆清漆层 |
| 0.25–0.45 | 半哑 | 拉丝金属、塑料 |
| 0.45–0.65 | 哑光 | ABS、皮革、木材 |
| 0.65–0.85 | 很哑 | 混凝土、织物 |
| 0.85–1.0 | 完全漫射 | 橡胶、毛毡 |

### 环境贴图（IBL）

**金属没有环境贴图就是黑的。** 因为金属的可见颜色几乎全部来自反射，没有环境就没有可反射的东西。

```js
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const pmrem = new THREE.PMREMGenerator(renderer);
const envRT = pmrem.fromScene(new RoomEnvironment(), 0.04);
scene.environment = envRT.texture;
pmrem.dispose();
```

`RoomEnvironment` 是程序化生成的影棚环境，零外部文件——**单文件交付必用**。第二个参数是模糊量（sigma），0.02–0.06 之间。

---

## 二、金属配方

```js
const M = (color, roughness, extra = {}) => new THREE.MeshPhysicalMaterial({
  color, metalness: 1.0, roughness, envMapIntensity: 1.0, ...extra,
});
```

| 材质 | color | roughness | 备注 |
|---|---|---|---|
| 抛光铝 | `#d8dde2` | 0.14 | 最常用的"科技白金属" |
| 拉丝铝 | `#c4cad0` | 0.34 | 加 `anisotropy: 0.6` 才有拉丝方向感 |
| 不锈钢 | `#b8bec4` | 0.26 | 比铝略暗、略冷 |
| 阳极氧化黑 | `#2a2e33` | 0.42 | 消费电子的标志性质感 |
| 黄铜 | `#d4a24c` | 0.22 | 暖金，别用纯 `#ffd700`（太艳） |
| 紫铜 | `#c06a35` | 0.20 | 电机线圈、散热底座 |
| 钛合金 | `#8a9099` | 0.30 | 冷灰偏蓝 |
| 铬 | `#e8ecef` | 0.04 | 镜面，必须有好环境否则像塑料 |
| 铸铁 | `#3a3d42` | 0.72 | metalness 0.85（有氧化层） |
| 枪灰 | `#4a4f55` | 0.38 | 机械件通用 |

```js
const aluminum = M('#d8dde2', 0.14);
const steel    = M('#b8bec4', 0.26);
const copper   = M('#c06a35', 0.20);
const castIron = new THREE.MeshPhysicalMaterial({
  color: '#3a3d42', metalness: 0.85, roughness: 0.72,
});
```

### 金属漆（车漆）

需要**三层**：底色 + 金属颗粒 + 清漆。

```js
const carPaint = new THREE.MeshPhysicalMaterial({
  color: '#101a26',
  metalness: 0.9,
  roughness: 0.25,
  clearcoat: 1.0,
  clearcoatRoughness: 0.06,
  envMapIntensity: 1.2,
});
```

`clearcoat` 是独立的高光层，这是"车漆"和"塑料"的差别所在。`clearcoatRoughness` 一定要小于 0.1，否则清漆层糊掉。

---

## 三、塑料与橡胶

| 材质 | metalness | roughness | 其他 |
|---|---|---|---|
| ABS 哑光 | 0 | 0.62 | 最常见的外壳塑料 |
| ABS 亮面 | 0 | 0.28 | 加 `clearcoat: 0.4` |
| PC 透明 | 0 | 0.05 | `transmission: 0.95, thickness: 0.01, ior: 1.58` |
| 亚克力 | 0 | 0.08 | `transmission: 0.9, ior: 1.49` |
| 硅胶 | 0 | 0.75 | 略透 `transmission: 0.15` |
| 橡胶 | 0 | 0.92 | 颜色别用纯黑 `#000`，用 `#121417` |
| 轮胎 | 0 | 0.88 | `#080a0d` + 微弱 sheen |

```js
const absMatte  = new THREE.MeshPhysicalMaterial({ color: '#e8e8e8', metalness: 0, roughness: 0.62 });
const rubber    = new THREE.MeshPhysicalMaterial({ color: '#121417', metalness: 0, roughness: 0.92 });
const clearPC   = new THREE.MeshPhysicalMaterial({
  color: '#ffffff', metalness: 0, roughness: 0.05,
  transmission: 0.95, thickness: 0.01, ior: 1.58, transparent: true,
});
```

> **`transmission` 很贵**：它会让 three 额外渲染一张背景纹理（transmissionRenderTarget），相当于多一遍场景。只在 1–2 个关键物体上用。普通"看起来像玻璃"用 `transparent: true + opacity: 0.3` 就够，成本低一个数量级。

---

## 四、玻璃的两种做法

### 便宜的假玻璃（推荐用于单文件场景）

```js
const fakeGlass = new THREE.MeshPhysicalMaterial({
  color: '#9fe4ff',
  metalness: 0.1,
  roughness: 0.06,
  transparent: true,
  opacity: 0.3,
  depthWrite: false,        // 关键：避免玻璃遮挡内部透明排序错乱
  side: THREE.DoubleSide,
  envMapIntensity: 1.6,
});
```

### 物理玻璃（少量使用）

```js
const realGlass = new THREE.MeshPhysicalMaterial({
  color: '#ffffff', metalness: 0, roughness: 0.02,
  transmission: 1.0, thickness: 0.02, ior: 1.52,
  transparent: true,
});
```

### 透明排序三原则

1. `transparent: true` 的物体按到相机距离排序，**相互穿插时会闪**。
2. 玻璃类设 `depthWrite: false`，让它不写深度，靠 `renderOrder` 控制先后。
3. 需要"看到内部"时，把外壳 `renderOrder` 设大（最后画），内部物体正常画。

```js
glass.renderOrder = 6;
shell.renderOrder = 8;
```

---

## 五、陶瓷 / 石材 / 建筑

| 材质 | metalness | roughness | 其他 |
|---|---|---|---|
| 白瓷 | 0 | 0.10 | `clearcoat: 1, clearcoatRoughness: 0.03` |
| 陶土 | 0 | 0.78 | `#b8846a` |
| 清水混凝土 | 0 | 0.90 | `#8a8a86` + 轻微噪声粗糙度 |
| 大理石 | 0 | 0.18 | 需要纹理，纯色不像 |
| 沥青 | 0 | 0.95 | `#1a1a1c` |
| 石膏 | 0 | 0.85 | `#e0dedb` |

---

## 六、有机材质

| 材质 | metalness | roughness | 其他 |
|---|---|---|---|
| 木材（哑光） | 0 | 0.65 | 必须有木纹贴图 |
| 木材（漆面） | 0 | 0.25 | `clearcoat: 0.8` |
| 皮革 | 0 | 0.55 | 需要法线贴图 |
| 织物 | 0 | 0.88 | `sheen: 0.4, sheenColor: '#ffffff'` |
| 皮肤 | 0 | 0.45 | `sheen: 0.2` + 次表面散射（成本高，慎用） |

`sheen` 是织物/绒毛的关键参数，它模拟纤维边缘的散射光。没有 sheen 的织物看起来像塑料布。

---

## 七、特殊效果

### 碳纤维

```js
const carbon = new THREE.MeshPhysicalMaterial({
  color: '#0a0e13', metalness: 0.6, roughness: 0.3,
  clearcoat: 1.0, clearcoatRoughness: 0.08,
  // 配 weaveTexture() 作为 roughnessMap 才像
});
```

### 自发光

```js
const led = new THREE.MeshStandardMaterial({
  color: '#0a1418',            // 底色压暗，否则发光不明显
  emissive: '#38f2ff',
  emissiveIntensity: 2.0,
  metalness: 0,
  roughness: 0.5,
});
```

**自发光不会照亮别的物体**（除非配 PointLight 或后处理 bloom）。想有光晕就加 `UnrealBloomPass`。

### 全息 / 扫描线

```js
const hologram = new THREE.MeshBasicMaterial({
  color: '#38f2ff', transparent: true, opacity: 0.35,
  side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false,
});
```

`AdditiveBlending` + `depthWrite: false` 是"科技发光面"的标准组合。

### 线框

```js
const wire = new THREE.LineSegments(
  new THREE.EdgesGeometry(geometry, 26),   // 26° 是"只保留硬边"的常用阈值
  new THREE.LineBasicMaterial({ color: '#38f2ff', transparent: true, opacity: 0.5 })
);
```

用 `EdgesGeometry` 而不是 `WireframeGeometry`：前者只画结构边，后者画三角剖分的所有边（会很乱很密）。

---

## 八、程序化贴图（单文件必需）

单文件交付不能带图片文件，所以粗糙度/法线细节必须用 canvas 生成。

### 噪声粗糙度

```js
function noiseTexture(size = 128, contrast = 0.5, seed = 20260101) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  const img = ctx.createImageData(size, size);
  let s = seed;
  const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < size * size; i++) {
    const v = 128 + (rnd() - 0.5) * 255 * contrast;
    img.data[i * 4] = img.data[i * 4 + 1] = img.data[i * 4 + 2] = v;
    img.data[i * 4 + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.NoColorSpace;   // 数据贴图不能设 SRGB
  return tex;
}
```

### 拉丝金属

```js
function brushedTexture(size = 256, seed = 7) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  let s = seed;
  const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  ctx.fillStyle = '#808080';
  ctx.fillRect(0, 0, size, size);
  for (let i = 0; i < size * 3; i++) {
    const y = rnd() * size;
    const v = 96 + rnd() * 96;
    ctx.strokeStyle = `rgb(${v},${v},${v})`;
    ctx.globalAlpha = 0.12 + rnd() * 0.2;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(size, y + (rnd() - 0.5) * 2);
    ctx.stroke();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(2, 2);
  tex.colorSpace = THREE.NoColorSpace;
  return tex;
}
// 用法：mat.roughnessMap = brushedTexture(); mat.roughness = 1.0;  // 让贴图控制实际值
```

### 编织（碳纤维）

```js
function weaveTexture(size = 256, cell = 16, seed = 3) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  let s = seed;
  const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let y = 0; y < size; y += cell) {
    for (let x = 0; x < size; x += cell) {
      const over = ((x / cell) + (y / cell)) % 2 === 0;
      const v = over ? 150 + rnd() * 30 : 90 + rnd() * 30;
      ctx.fillStyle = `rgb(${v},${v},${v})`;
      ctx.fillRect(x, y, cell, cell);
      // 纤维方向纹理
      ctx.globalAlpha = 0.18;
      ctx.fillStyle = '#fff';
      if (over) ctx.fillRect(x, y + cell * 0.3, cell, cell * 0.16);
      else ctx.fillRect(x + cell * 0.3, y, cell * 0.16, cell);
      ctx.globalAlpha = 1;
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.NoColorSpace;
  return tex;
}
```

### 接触阴影贴图

```js
function shadowTexture(size = 256) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, 'rgba(0,0,0,0.55)');
  g.addColorStop(0.45, 'rgba(0,0,0,0.22)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(c);
}
```

比实时阴影便宜 100 倍，观感差距在"物体不动"时几乎看不出来。

---

## 九、色彩管理（只做一次）

```js
renderer.outputColorSpace = THREE.SRGBColorSpace;   // 默认已是，别重复设
renderer.toneMapping = THREE.ACESFilmicToneMapping; // 电影感
renderer.toneMappingExposure = 1.0;                 // 0.85–1.15 之间微调
```

**规则**：

- `outputColorSpace` 和 `toneMapping` 各只赋一次。重复赋值 = 双重转换 = 画面发灰。
- 颜色贴图（map / emissiveMap）设 `texture.colorSpace = THREE.SRGBColorSpace`。
- 数据贴图（roughnessMap / normalMap / aoMap / metalnessMap）设 `THREE.NoColorSpace`，**绝不能设 SRGB**，否则数据被当颜色转换，材质会明显错。

---

## 十、常见错误

| 症状 | 原因 | 修法 |
|---|---|---|
| 金属是黑的 | 没有环境贴图 | 加 `scene.environment`（PMREM + RoomEnvironment） |
| 画面发灰 | `toneMapping` 设了两次 | 只设一次 |
| 塑料看起来像金属 | `metalness` 给了 0.5 | 非金属给 0 |
| 所有东西都像塑料 | 没有 roughness 差异 | 拉开粗糙度区间，别都用 0.5 |
| 玻璃后面一片黑 | 透明排序错 | 玻璃 `depthWrite: false` + `renderOrder` |
| 材质边缘有锯齿状黑边 | 法线贴图 colorSpace 错 | 数据贴图设 `NoColorSpace` |
| 模型加载后一片死白 | 贴图 colorSpace 没设 SRGB | 颜色贴图设 `SRGBColorSpace` |
| 帧率骤降 | 用了 `transmission` | 换成 `transparent + opacity` |

---

## 十一、自检

- [ ] 有环境贴图（金属才不会是黑的）
- [ ] `metalness` 只取 0 或 1（金属漆 0.9 例外）
- [ ] `roughness` 有明确档位，不是全部 0.5
- [ ] `toneMapping` / `outputColorSpace` 各只设一次
- [ ] 数据贴图 `colorSpace = NoColorSpace`
- [ ] `transmission` 使用数量 ≤ 2
- [ ] 透明物体设了 `depthWrite: false` 和 `renderOrder`
- [ ] 材质数量控制在 10 个以内（同材质复用）
