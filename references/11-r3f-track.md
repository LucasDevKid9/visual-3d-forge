# 11 · R3F 轨道

> React Three Fiber 不是"three.js 的 React 封装"，它是**用 React 的 reconciler 描述 three 对象树**。
> 理解这一点，很多"为什么这样写不生效"就有答案了。

---

## 一、先判断：该不该用 R3F

| 情况 | 选择 |
|---|---|
| 单个场景、一次性交付、需要单文件 | **不用** R3F（过度工程，D0/D1 更合适） |
| 场景需要复用组件（同一套零件在多个页面） | 用 |
| 需要和 React 应用状态（列表、筛选、表单）联动 | 用 |
| 多人长期迭代、需要组件测试 | 用 |
| 只是"想用现代技术栈" | **不用**。R3F 会引入构建链、依赖版本约束、SSR 问题 |

R3F 的价值在**组合**与**状态同步**，不在渲染性能。纯展示型三维用 R3F 是负收益。

---

## 二、版本约束（9.x）

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "three": "^0.187.0",
    "@react-three/fiber": "^9.8.0"
  }
}
```

- R3F 9.x 要求 **React ≥19 <19.4**。React 18 会直接报错。
- `three` 版本必须与 R3F 的 peer 兼容，不要跨大版本混用。
- 需要 helper 时再装 `@react-three/drei`；需要物理再装 `@react-three/rapier`。**不要一次性装全家桶**。

---

## 三、核心心智模型

### JSX 元素 = three 对象

```jsx
<mesh position={[0, 1, 0]}>
  <boxGeometry args={[1, 1, 1]} />
  <meshStandardMaterial color="#d8dde2" metalness={1} roughness={0.2} />
</mesh>
```

编译后等价于：

```js
const mesh = new THREE.Mesh();
mesh.position.set(0, 1, 0);
mesh.geometry = new THREE.BoxGeometry(1, 1, 1);
mesh.material = new THREE.MeshStandardMaterial({ color: '#d8dde2', metalness: 1, roughness: 0.2 });
```

- **小写标签** = three 内置对象
- **`args`** = 构造参数数组，**只在挂载时用一次**
- **`attach`** = 挂到父级的哪个属性（默认自动推断：geometry/material 自动 attach）

### `args` 是陷阱源头

```jsx
// 危险：width 变化会销毁旧 geometry、重建新的
<boxGeometry args={[width, 1, 1]} />
```

`args` 变化 → R3F 销毁旧对象、new 新对象。频繁变化（比如拖拽滑块）会导致每秒重建几十次几何。

**正确做法**：几何参数固定，用 `scale` 表达尺寸变化：

```jsx
<boxGeometry args={[1, 1, 1]} />
<mesh scale={[width, 1, 1]} />
```

### `attach` 的用法

```jsx
// 把材质挂到 mesh.material（默认已自动推断，一般不用写）
<mesh>
  <boxGeometry />
  <meshStandardMaterial attach="material" />
</mesh>

// 挂到非默认位置：给 mesh 加一个自定义属性
<mesh>
  <boxGeometry />
  <meshStandardMaterial attach="material-0" />  {/* 多材质数组的第 0 个 */}
</mesh>
```

---

## 四、`useFrame`：唯一的逐帧入口

```jsx
import { useFrame } from '@react-three/fiber';
import { useRef } from 'react';

function Spinner() {
  const ref = useRef();
  useFrame((state, delta) => {
    ref.current.rotation.y += delta * 0.5;
  });
  return <mesh ref={ref}><boxGeometry /><meshStandardMaterial /></mesh>;
}
```

### 三条铁律

**1. 绝不在 `useFrame` 里 `setState`**

```jsx
// 错：每帧触发 React 重渲染，必掉帧
useFrame(() => setCount(c => c + 1));

// 对：直接改对象
useFrame(() => { ref.current.rotation.y += 0.01; });
```

需要显示数字时，用 `ref` 直接改 DOM 文本，或降低更新频率（比如每 10 帧一次）。

**2. 绝不在 `useFrame` 里 `new`**

```jsx
// 错：每帧分配，GC 抖动
useFrame(() => {
  const v = new THREE.Vector3();
  ref.current.position.copy(v);
});

// 对：模块级或 useMemo 复用
const _v = new THREE.Vector3();
useFrame(() => { ref.current.position.copy(_v); });
```

**3. 依赖 `delta` 而不是固定增量**

```jsx
// 错：帧率不同速度不同
useFrame(() => { ref.current.rotation.y += 0.01; });

// 对：与帧率无关
useFrame((_, delta) => { ref.current.rotation.y += delta * 0.6; });
```

`delta` 在高负载时可能很大（切标签页回来），要钳制：

```jsx
useFrame((_, delta) => {
  const dt = Math.min(delta, 0.05);
  ...
});
```

---

## 五、Canvas 配置

```jsx
<Canvas
  dpr={[1, 2]}                              // 像素比上下限，等价于 setPixelRatio(Math.min(devicePixelRatio, 2))
  camera={{ position: [4, 3, 6], fov: 38 }} // 等价于 PerspectiveCamera 参数
  shadows                             // 开启阴影贴图
  gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
  frameloop="demand"                  // 按需渲染（静止时不画）
>
  <Scene />
</Canvas>
```

### `frameloop` 三档

| 值 | 行为 | 适用 |
|---|---|---|
| `"always"` | 每帧渲染（默认） | 有持续动画 |
| `"demand"` | 只在 `invalidate()` 时渲染 | 静态展示、交互驱动 |
| `"never"` | 完全不渲染 | 手动控制 |

`demand` 模式能省掉 90% 的空转功耗，但**任何动画都必须手动 `invalidate()`**，否则画面不动。

---

## 六、资源生命周期

### R3F 自动 dispose

R3F 会在组件卸载时自动 `dispose()` 由 JSX 创建的 geometry / material / texture。**但有三类不会**：

1. `useMemo` 里 `new` 出来的对象（R3F 不知道它属于谁）
2. 模块级单例
3. 从外部传入的对象

```jsx
// 需要手动清理
function Custom() {
  const geo = useMemo(() => new THREE.BufferGeometry(), []);
  useEffect(() => () => geo.dispose(), [geo]);
  return <mesh geometry={geo} />;
}
```

### 跨 Canvas 共享材质

**不要**把一个材质对象同时给两个 `<Canvas>` 用。每个 Canvas 有独立的 WebGL 上下文，材质内部缓存的是 renderer 相关状态，共享会导致其中一个渲染异常。

---

## 七、事件系统

R3F 内置 raycaster，事件名与 DOM 类似：

```jsx
<mesh
  onClick={(e) => { e.stopPropagation(); select(e.object.name); }}
  onPointerOver={(e) => { e.stopPropagation(); setHover(true); }}
  onPointerOut={() => setHover(false)}
>
```

要点：

- **`e.stopPropagation()` 必须调**，否则会穿透到后面的物体。
- 事件基于 raycaster，**对 `Points` / `Line` 需要设 `raycast` 容差**（`<points raycast={...}>`）。
- 大量物体时 raycast 成本高，用 `@react-three/drei` 的 `<Bvh>` 加速。

---

## 八、加载资源

```jsx
import { useLoader } from '@react-three/fiber';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { Suspense } from 'react';

function Model() {
  const gltf = useLoader(GLTFLoader, '/model.glb');
  return <primitive object={gltf.scene} />;
}

<Suspense fallback={null}>
  <Model />
</Suspense>
```

`useLoader` 走 Suspense，**必须包 `<Suspense>`**，否则整个 Canvas 白屏。

`<primitive object={...} />` 用于挂载"已存在的 three 对象"（加载的模型、外部构造的对象）。注意：`<primitive>` 不会自动 dispose 传入对象。

---

## 九、常见陷阱

| 症状 | 原因 | 修法 |
|---|---|---|
| 改 `args` 后闪烁/卡顿 | `args` 变化触发重建 | 固定 `args`，用 `scale`/`position` 表达变化 |
| 动画不动 | `frameloop="demand"` 但没 `invalidate` | 每帧调 `invalidate()` 或改回 `always` |
| 掉帧严重 | `useFrame` 里 setState | 改 ref |
| 内存持续增长 | `useMemo` 对象没 dispose | `useEffect` 返回清理函数 |
| StrictMode 下双份对象 | React 19 开发模式双调用 | 用 `useMemo` + 幂等构造，或接受开发期现象 |
| 材质在两个 Canvas 间错乱 | 跨上下文共享材质 | 每个 Canvas 独立创建 |
| 模型加载后全黑 | 没有环境光/环境贴图 | 加 `<Environment preset="studio" />` 或 PMREM |
| 事件穿透 | 没调 `stopPropagation` | 每个 handler 首行调 |
| 首屏空白很久 | 大模型阻塞 | `<Suspense fallback={<Loader/>}>` + 分块加载 |

---

## 十、最小完整工程

```
r3f-app/
├── package.json
├── vite.config.js
├── index.html
└── src/
    ├── main.jsx
    ├── App.jsx
    └── Scene.jsx
```

`package.json`：

```json
{
  "name": "v3d-r3f-app",
  "private": true,
  "type": "module",
  "scripts": { "dev": "vite", "build": "vite build", "preview": "vite preview" },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "three": "^0.187.0",
    "@react-three/fiber": "^9.8.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^6.0.0"
  }
}
```

`Scene.jsx`：

```jsx
import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export default function Scene() {
  const group = useRef();

  const materials = useMemo(() => ({
    metal: new THREE.MeshPhysicalMaterial({
      color: '#d8dde2', metalness: 1, roughness: 0.18, envMapIntensity: 1.0,
    }),
    dark: new THREE.MeshPhysicalMaterial({
      color: '#12161c', metalness: 0.2, roughness: 0.55,
    }),
  }), []);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    if (group.current) group.current.rotation.y += dt * 0.4;
  });

  return (
    <group ref={group}>
      <mesh material={materials.metal} castShadow>
        <torusKnotGeometry args={[0.8, 0.26, 160, 24]} />
      </mesh>
      <mesh position={[0, -1.1, 0]} material={materials.dark} receiveShadow>
        <cylinderGeometry args={[1.4, 1.5, 0.12, 64]} />
      </mesh>
    </group>
  );
}
```

`App.jsx`：

```jsx
import { Canvas } from '@react-three/fiber';
import { Environment, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import Scene from './Scene';

export default function App() {
  return (
    <Canvas
      dpr={[1, 2]}
      shadows
      camera={{ position: [3.2, 2.4, 4.2], fov: 38 }}
      gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
    >
      <color attach="background" args={['#070d14']} />
      <Environment preset="studio" />
      <ambientLight intensity={0.35} />
      <directionalLight position={[4, 6, 3]} intensity={2.2} castShadow />
      <directionalLight position={[-4, 2, -3]} intensity={0.9} color="#38f2ff" />
      <Scene />
      <OrbitControls
        enablePan={false}
        minDistance={3}
        maxDistance={9}
        minPolarAngle={Math.PI * 0.18}
        maxPolarAngle={Math.PI * 0.48}
      />
    </Canvas>
  );
}
```

`main.jsx`：

```jsx
import { createRoot } from 'react-dom/client';
import App from './App';

createRoot(document.getElementById('root')).render(<App />);
```

`index.html`：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>V3D · R3F</title>
  <style>
    html, body, #root { height: 100%; margin: 0; background: #070d14; }
    canvas { display: block; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
```

`vite.config.js`：

```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: { target: 'es2022', chunkSizeWarningLimit: 1200 },
});
```

---

## 十一、性能预算

| 项目 | 建议值 |
|---|---|
| `dpr` | `[1, 2]`，移动端 `[1, 1.5]` |
| 三角面 | < 200k（中端） / < 500k（桌面独显） |
| 绘制调用 | < 150 |
| 材质数 | < 15 |
| 光源数 | ≤ 3 个实时投影光 |
| 纹理总显存 | < 128MB |

超过时的手段（按性价比排序）：

1. `InstancedMesh`（同类物体 >30）
2. 合并几何（`mergeGeometries`）
3. 降 `dpr`
4. 关闭实时阴影，改贴图假阴影
5. LOD
6. 贴图压缩（KTX2）

---

## 十二、自检

- [ ] React ≥19、R3F 9.x、three 0.187.x 版本匹配
- [ ] `useFrame` 内无 `setState`、无 `new`
- [ ] 所有动画用 `delta` 且已钳制
- [ ] `args` 不含高频变化的变量
- [ ] `useMemo` 创建的对象有 dispose 清理
- [ ] `useLoader` 外层有 `<Suspense>`
- [ ] 事件 handler 调了 `stopPropagation`
- [ ] `dpr` 已设上限
- [ ] `validate_scene.py` 对构建产物无 FAIL
