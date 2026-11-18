# 17 · 从 react-three-fiber 9.8.1 提炼的可迁移模式

> R3F 是 React 的 three.js 渲染器（reconciler 架构）。本 Skill 的交付契约是
> **单文件、无框架依赖**，所以不引入 R3F 运行时。但它的源码里有五个工程模式，
> 用原生 three 复刻后能显著提升质量。本文给的是**可复制的原生实现**。
>
> 本文讲**把 R3F 的做法搬到原生 three**，适用 D0/D1/D2 档。
> 如果你确实要上 React 工程（D3），看 [`16-r3f-track.md`](16-r3f-track.md)。

---

## 模式一：按需渲染（demand frameloop）

### R3F 怎么做的

`core/store.ts` 定义 `Frameloop = 'always' | 'demand' | 'never'`；
`core/loop.ts` 用 `frames` 计数器控制：

```ts
// loop.ts 真实源码（节选）
if (state.frameloop === 'always' || state.internal.frames > 0) {
  repeat += update(timestamp, state)
}
if (repeat === 0) { running = false; return cancelAnimationFrame(frame) }
```

`invalidate()` 把 `frames` 置 1 并重新启动 rAF。**没有变化就彻底停掉循环**。

### 为什么重要

持续 rAF 在笔记本上会让 GPU 常驻高功耗，风扇起飞、电池掉电。产品展示页
在用户不动的时候画面是静止的，完全没有必要 60fps 空转。

### 原生实现

```js
// ── 按需渲染调度器 ──────────────────────────────
let rafId = null;
let dirty = 2;                 // 待渲染帧数（2 = 双帧，避免首帧资源未就绪）
let continuous = false;        // 有持续动画时置 true

function invalidate(n = 1) {
  dirty = Math.min(60, dirty + n);
  if (rafId === null) rafId = requestAnimationFrame(loop);
}

function loop(t) {
  rafId = null;
  timer.update(t);
  const dt = Math.min(timer.getDelta(), 0.05);

  if (continuous) updateAnimation(dt);   // 只有持续动画才每帧算

  if (dirty > 0) {
    renderer.render(scene, camera);
    dirty--;
  }

  // 还有事要做才继续请求下一帧
  if (continuous || dirty > 0) rafId = requestAnimationFrame(loop);
}

// 任何改变画面的操作都调 invalidate()
controls.addEventListener('change', () => invalidate());
window.addEventListener('resize', () => { resize(); invalidate(); });
// 交互式高亮、材质切换、相机过渡结束……都调 invalidate()
```

**验收标准**：静止 3 秒后 `renderer.info.render.frame` 不再增长，任务管理器 GPU 占用归零。

**什么时候必须 `continuous = true`**：旋转、粒子、流体、着色器 time uniform、
自动巡航。纯静态展示 + 拖拽交互用 demand 就够。

---

## 模式二：帧回调优先级队列

### R3F 怎么做的

`useFrame(cb, priority)` 的 priority 越小越先执行；`priority > 0` 时 R3F **不自动渲染**，
把渲染控制权交给用户（用于后处理等自定义管线）。

### 为什么重要

物理更新必须在动画之前，相机跟随必须在动画之后，后处理必须在渲染之后。
没有顺序约定，就会出现"相机抖动一帧"、"粒子追不上发射器"这类玄学 bug。

### 原生实现

```js
const frameQueue = [];   // { order, fn, once }

function onFrame(order, fn, once = false) {
  frameQueue.push({ order, fn, once });
  frameQueue.sort((a, b) => a.order - b.order);
  return () => {
    const i = frameQueue.indexOf(frameQueue.find(x => x.fn === fn));
    if (i >= 0) frameQueue.splice(i, 1);
  };
}

// 约定俗成的 order 分段
const ORDER = {
  INPUT: 0,       // 输入采样
  PHYSICS: 10,    // 物理/碰撞
  ANIMATION: 20,  // 关键帧/程序动画
  CAMERA: 30,     // 相机跟随
  POST: 40,       // 后处理参数
  RENDER: 100,    // 渲染（通常不注册，由主循环负责）
};

// 主循环内
for (const item of frameQueue) {
  item.fn(dt, elapsed);
  if (item.once) item.dead = true;
}
frameQueue = frameQueue.filter(x => !x.dead);
```

**替代方案**：如果只有 2–3 个回调，直接按顺序写死更清晰。这个模式在
回调数 ≥ 4 或需要动态增删时才值得引入。

---

## 模式三：指针事件冒泡与捕获

### R3F 怎么做的

`core/events.ts` 561 行，核心流程：

```
raycaster 求交 → 按 distance 排序 → 去重 → 从命中对象向上冒泡
→ 找 eventObject → 若被 capture，把捕获目标并入命中集 → 派发监听器
```

支持 `onPointerDown` / `onPointerOver` / `onClick` / `stopPropagation` / `setPointerCapture`，
语义与 DOM 事件一致。

### 为什么重要

直接 `raycaster.intersectObjects(scene.children, true)` 然后取 `[0]` 有三个问题：
① 会命中辅助线/网格等不该交互的对象；② 嵌套组里的子网格无法让父组统一响应；
③ 无法实现"点到空白处取消选中"。

### 原生实现

```js
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const pickables = [];              // 只把可交互对象放进来

function updatePointer(e) {
  const r = renderer.domElement.getBoundingClientRect();
  pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
}

function dispatch(type, e) {
  updatePointer(e);
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(pickables, false);
  if (!hits.length) { emit('miss', null); return; }

  const hit = hits[0];
  const path = [];
  for (let o = hit.object; o; o = o.parent) path.push(o);   // 叶 → 根

  let stopped = false;
  const ev = { ...hit, stopPropagation: () => { stopped = true; } };

  // 捕获阶段：根 → 叶
  for (let i = path.length - 1; i >= 0 && !stopped; i--) {
    path[i].userData[`on${type}Capture`]?.(ev);
  }
  // 冒泡阶段：叶 → 根
  for (let i = 0; i < path.length && !stopped; i++) {
    path[i].userData[`on${type}`]?.(ev);
  }
}

renderer.domElement.addEventListener('pointerdown', e => dispatch('PointerDown', e));
renderer.domElement.addEventListener('pointermove', e => dispatch('PointerMove', e));
renderer.domElement.addEventListener('click',      e => dispatch('Click', e));
```

**用法**

```js
const gear = new THREE.Mesh(geo, mat);
gear.userData.onClick = (e) => {
  e.stopPropagation();          // 阻止父组也响应
  select(gear);
  invalidate();
};
group.userData.onClick = () => { /* 兜底：点到组内任何部件 */ };
```

**性能**：`pointermove` 里做 raycast 成本高，用节流或只在 `pointerdown` 时求交。

---

## 模式四：自动资源释放

### R3F 怎么做的

`core/reconciler.tsx` 的 `detach` 在对象从树中移除时，自动调用
`geometry.dispose()` / `material.dispose()` / `texture.dispose()`，
并通过 `dispose` 参数允许用户接管。

### 为什么重要

three 的 GPU 资源**不受 JS GC 管理**。反复创建/销毁场景而不 dispose，
显存会持续上涨直到 context lost（页面黑屏，且无法恢复）。

### 原生实现

```js
function disposeObject(root) {
  const textures = new Set();
  root.traverse((o) => {
    if (o.geometry) o.geometry.dispose();

    const mats = o.material ? (Array.isArray(o.material) ? o.material : [o.material]) : [];
    for (const m of mats) {
      for (const key of Object.keys(m)) {
        const v = m[key];
        if (v && v.isTexture) textures.add(v);
      }
      // uniforms 里的贴图
      if (m.uniforms) {
        for (const u of Object.values(m.uniforms)) {
          if (u?.value?.isTexture) textures.add(u.value);
        }
      }
      m.dispose();
    }
  });
  // 去重后统一释放（同一贴图被多材质共享时只释放一次）
  textures.forEach(t => t.dispose());
  textures.clear();
}

// 切换场景
function swapScene(next) {
  disposeObject(current);
  scene.remove(current);
  current = next;
  scene.add(current);
  invalidate();
}
```

**用 `Set` 去重**是关键：共享贴图重复 dispose 会让其他材质变黑。

---

## 模式五：声明式场景装配

### R3F 怎么做的

JSX 树即场景图，reconciler 把 `<mesh>` 映射为 `new THREE.Mesh()`，
`attach="material"` 决定挂到父对象的哪个属性。

### 为什么重要

当场景由**数据驱动**（配置表、接口返回、参数化生成）时，手写命令式装配会变成
几百行重复代码，且难以做"只更新变化的节点"。

### 原生实现

```js
const REGISTRY = {
  group:    (p) => new THREE.Group(),
  mesh:     (p) => new THREE.Mesh(buildGeometry(p.geometry), buildMaterial(p.material)),
  line:     (p) => new THREE.Line(buildGeometry(p.geometry), buildMaterial(p.material)),
  points:   (p) => new THREE.Points(buildGeometry(p.geometry), buildMaterial(p.material)),
  light:    (p) => new THREE[p.type](p.color ?? 0xffffff, p.intensity ?? 1),
  camera:   (p) => new THREE.PerspectiveCamera(p.fov ?? 40, p.aspect ?? 1, p.near ?? 0.1, p.far ?? 100),
};

function build(spec) {
  const node = REGISTRY[spec.kind](spec.props ?? {});
  const { position, rotation, scale } = spec.props ?? {};
  if (position) node.position.fromArray(position);
  if (rotation) node.rotation.fromArray(rotation);
  if (scale) typeof scale === 'number' ? node.scale.setScalar(scale) : node.scale.fromArray(scale);
  if (spec.name) node.name = spec.name;
  if (spec.userData) Object.assign(node.userData, spec.userData);

  for (const child of spec.children ?? []) node.add(build(child));
  return node;
}

// 使用
const spec = {
  kind: 'group', name: 'gearbox',
  children: [
    { kind: 'mesh', name: 'housing',
      props: { geometry: ['cylinder', 1.2, 1.2, 0.6, 48], material: { color: 0x8a8f98, metalness: 1, roughness: 0.35 } } },
    { kind: 'mesh', name: 'shaft',
      props: { geometry: ['cylinder', 0.18, 0.18, 1.6, 24], material: { color: 0xc9ced6, metalness: 1, roughness: 0.2 }, rotation: [Math.PI/2, 0, 0] } },
  ],
};
scene.add(build(spec));
```

**这个模式适合**：参数化零件库、教学演示（切换配置）、从 JSON 恢复场景。
**不适合**：一次性手写场景——直接写命令式代码更短更直观。

---

## 附：什么时候该用真正的 R3F

| 判据 | 用原生 three（本 Skill） | 用 React + R3F |
|---|---|---|
| 交付形态 | 单文件 HTML、双击即开 | 已有 React 工程 |
| 依赖 | 零框架依赖 | 可接受 node_modules |
| 状态管理 | 少量局部状态 | 复杂表单/路由/权限 |
| 场景变化 | 静态或简单交互 | 频繁增删改对象、列表驱动 |
| 团队 | 单人或交付给非开发者 | 前端团队长期迭代 |
| 性能 | 可精细控制 | reconciler 有额外开销 |

**结论**：本 Skill 的场景是"交付一个能打开就看的 3D 页面"，原生 three 是正确选择。
R3F 的价值在**模式**，不在运行时。

---

## 附：R3F 9.8.1 源码地图（需要深挖时看这里）

```
packages/fiber/src/core/
├── reconciler.tsx   836行  自定义 reconciler，对象创建/更新/销毁
├── events.ts        561行  指针事件系统（冒泡、捕获、优先级）
├── utils.tsx        538行  属性应用、attach 语义
├── configuration.ts 345行  默认配置、扩展
├── store.ts         340行  状态容器、frameloop、dpr
├── root.tsx         275行  渲染根、挂载
├── hooks.tsx        173行  useFrame / useThree / useLoader
├── loop.ts          168行  rAF 调度、invalidate、全局 effects
├── portal.tsx       132行  跨场景 portal
├── renderer.ts       50行  渲染器包装
└── extend.ts         36行  注册自定义类

packages/fiber/src/web/
├── Canvas.tsx       215行  DOM 容器、resize、事件绑定
└── events.ts         66行  createPointerEvents

docs/API/          canvas / events / hooks / objects / typescript / testing
docs/advanced/     pitfalls / scaling-performance
```
