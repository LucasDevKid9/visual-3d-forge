# 23 · 官方示例图谱：从 three.js r187 gallery 反推可复用模式

> 数据来源：r187 标签 `examples/` 下 583 个官方示例（WebGL / WebGPU / physics / webaudio / misc）。
> 方法：每个示例只读四件事——**import 行、构造顺序、循环里的更新、销毁方式**。
> 本文把反复出现的模式压成可直接抄的 idiom，并标注本技能的覆盖状态。addon 是否在内置 vendor 里，查 `12-addons-catalog.md`。

## 一、怎么反推一个官方示例

```
1. HTML 里只有一个 <script type="module">，其余都是壳。
2. import 行 → 用了哪些 addon（决定依赖闭包）。
3. init() 顺序：scene/camera/renderer → 环境与光 → 模型/几何 → 控件/交互 → 后处理。
4. animate() 循环：mixer.update(dt) / controls.update() / physics.step() / composer.render()。
5. 不能复制的部分：外部模型路径、音频文件、WASM 解码器、texture 资源——换成本地占位或程序化生成。
```

示例之间可移植的是**结构与 API 用法**，不是素材。抄模式时把模型路径换成占位几何体或本任务的构件树。

## 二、能力图谱（12 类）

### A 模型加载与骨骼动画

官方示例：`webgl_loader_gltf`、`webgl_animation_keyframes`、`webgl_animation_skinning_morph`、`webgl_animation_skinning_ik`、`webgl_morphtargets_horse`

**加载管线（可选压缩插件，按需 set）**

```js
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const loader = new GLTFLoader();
loader.setDRACOLoader(new DRACOLoader().setDecoderPath('three/addons/libs/draco/'));
loader.setKTX2Loader(new KTX2Loader().detectSupport(renderer));
loader.setMeshoptDecoder(MeshoptDecoder);

const gltf = await loader.loadAsync(url);
scene.add(gltf.scene);
```

**动画剪辑**

```js
const mixer = new THREE.AnimationMixer(gltf.scene);
mixer.clipAction(gltf.animations[0]).play();
// 循环里：mixer.update(delta);
```

- 多角色同模型：用 `SkeletonUtils.clone(scene)` 克隆骨骼，不要直接 `scene.clone()`（骨骼会共享）。
- IK：`animation/CCDIKSolver.js` + `CCDIKHelper`，每帧 `ikSolver.update()`。
- 形态目标：直接喂 `gltf.animations`；逐帧插值用 `morphTargetInfluences[i]`。
- DRACO/KTX2 为按需插件（解码器是运行时资产）；FBX 需 fflate，按需。

### B 后处理链

官方示例：`webgl_postprocessing_unreal_bloom`、`webgl_postprocessing_ssao`、`webgl_postprocessing_3dlut`

**顺序铁律**：`RenderPass` → 中间效果 pass → **`OutputPass` 必须最后**（色彩空间与色调映射收尾）。不要在链外再调一次输出编码。

```js
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js';
import { LUTPass } from 'three/addons/postprocessing/LUTPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));

const bloom = new UnrealBloomPass(new THREE.Vector2(w, h), 1.0, 0.5, 0.85);
composer.addPass(bloom);

const ssao = new SSAOPass(scene, camera, w, h);   // 桌面端才开，移动端降级到接触阴影
composer.addPass(ssao);

const lut = new LUTPass();                           // 调色：LUT3dl / LUTCube / LUTImage 三选一
composer.addPass(lut);

composer.addPass(new OutputPass());
// 循环里：composer.render(); 不要再 renderer.render(scene, camera)
```

- `OutlinePass`：选中态描边；`FilmPass`：颗粒/扫描线；`BokehPass`：景深（贵，慎开）。
- 后处理是加成不是前提：直接光 + 阴影 + IBL + 单次 tone mapping 已决定大部分画质。

### C 实例化与散布

官方示例：`webgl_instancing_dynamic`、`webgl_instancing_scatter`、`webgl_raycaster_bvh`、`webgl_loader_gltf_instancing`

**动态 InstancedMesh（千级物体不重复建 mesh）**

```js
const dummy = new THREE.Object3D();
const inst = new THREE.InstancedMesh(geo, mat, count);
for (let i = 0; i < count; i++) {
  dummy.position.set(...); dummy.rotation.set(...); dummy.updateMatrix();
  inst.setMatrixAt(i, dummy.matrix);
  inst.setColorAt(i, color);          // instanceColor，需要时才用
}
inst.instanceMatrix.needsUpdate = true;
scene.add(inst);
// 循环里改 dummy → setMatrixAt → inst.instanceMatrix.needsUpdate = true
```

- 表面散布：`MeshSurfaceSampler` 先采样点，再喂 dummy。
- 远处模型：`THREE.LOD` 分 `addLevel(mesh, distance)`，循环里 `lod.update(camera)`。
- 合批：`BufferGeometryUtils.mergeGeometries` 把同材质静态几何合并。

### D 拾取与选择

官方示例：`webgl_interactive_cubes`、`webgl_interactive_cubes_gpu`、`webgl_raycaster_bvh`、`misc_boxselection`、`misc_controls_transform`

**射线拾取**

```js
const ray = new THREE.Raycaster();
const pointer = new THREE.Vector2();
function onPointerMove(e) {
  pointer.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
}
ray.setFromCamera(pointer, camera);
const hits = ray.intersectObjects(group.children, false);
```

- 大场景加速：BVH 先做包围盒再相交（按需 addon）。
- 框选：`SelectionBox` + `SelectionHelper`，`selectionBox.setFromPoints(pointerPoints)`，读 `selectBox.objects`。
- 物体内 DOM 标签：`InteractiveGroup` + `HTMLMesh`（3D 锚点 → DOM 投影）。
- 拖拽变换：`TransformControls`（轴/平面拖拽，挂到选中物体）；`DragControls`（平面拖拽）。

### E 控制方案

| 控件 | 场景 | 关键 API |
|---|---|---|
| `OrbitControls` | 产品/对象展示默认 | `enableDamping` `min/maxDistance` `min/maxPolarAngle` `enablePan` `target` |
| `MapControls` | 地图/俯瞰，左键平移 | 交互映射不同 |
| `PointerLockControls` | 第一人称漫游 | `lock()` `moveForward()` `moveRight()` |
| `FlyControls` | 自由飞行检视 | 位移 + 俯仰，无阻尼 |
| `TrackballControls` | 全向滚球 | 垂直也能翻 |
| `TransformControls` | 编辑器 | 与拾取配合 |

限位必须做：极角、距离、target 都设上下限，保证任何角度都是成立构图。

### F 环境与光照

官方示例：`webgl_lights_physical`、`webgl_shadowmap`、`webgl_shaders_sky`、`webgl_shaders_ocean`、`webgl_lensflares`、`webgl_instancing_dynamic`

**IBL（无 HDR 资产时）**

```js
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
```

- 天空：`objects/Sky.js` 配太阳方位；海面：`objects/Water.js`；镜面：`Reflector`；折射：`Refractor`。
- 镜头光斑：`Lensflare` + `LensflareElement`（贴图资产按需补）。
- 阴影：方向光 `castShadow`、`shadow.mapSize`、`shadow.camera` 左右上下；`ShadowMesh` 接收软影。
- 面光源：必须先 `RectAreaLightUniformsLib.init()`。

### G 几何与形变

官方示例：`webgl_geometries`、`webgl_geometry_shapes`、`webgl_decals`、`webgl_marchingcubes`、`webgl_clipping`

- 参数曲面：`ParametricGeometry((u,v,target)=>{}, 20, 20)`。
- 放样：`geometries/LoftGeometry.js`（截面链 → 车身/管材）。
- 贴花：`DecalGeometry(targetMesh, position, orientation, size)`，把 logo/划痕投影到曲面。
- 融球/流体：`MarchingCubes`，`addBall(x,y,z,strength,subtract,scale)`，`reset()` 清场。
- 粗线条：`Line2` + `LineGeometry` + `LineMaterial`（线宽以像素计，核心 `Line` 只有 1px）。
- 剖切：`renderer.clippingPlanes`（全局）或 `material.clippingPlanes`（局部）。
- 细分/减面：`TessellateModifier` / `SimplifyModifier`。

### H 粒子与 GPGPU

官方示例：`webgl_buffergeometry_custom_attributes_particles`、`webgl_points_billboards`、`webgl_gpgpu_birds`

**Points 自定义属性**

```js
const geo = new THREE.BufferGeometry();
geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
geo.setAttribute('aColor', new THREE.BufferAttribute(colors, 3));
const pts = new THREE.Points(geo, pointMaterial);
```

- Billboard 朝向：材质里用 `gl_PointSize` + 屏幕空间 sprite。
- GPGPU：`GPUComputationRenderer` 用两个纹理（读写交换）存状态，shader 里采样上一帧位置，CPU 不参与逐粒子更新。
- 粒子运动要继承对象已有的动势；凭空随机速度是屏保，不是生动。

### I 物理（按需，不进离线包）

官方示例：`physics_rapier_vehicle_controller`、`physics_ammo_cloth`、`physics_rapier_joints`、`physics_ammo_terrain`

```js
import { RapierPhysics } from 'three/addons/physics/RapierPhysics.js';
const physics = await new RapierPhysics().init();
// addBody(mesh, bodyType, colliderDesc) → 得到 body
// 循环里：physics.step(delta); 从 body 回写 mesh.position/quaternion
```

- 三个后端：Rapier（车体/角色/关节）、Ammo（布料/绳索/地形）、Jolt。
- **边界**：物理后端依赖运行时 WASM，**不打进离线包**；离线演示用手写质点弹簧/Verlet 替代（算法图谱 §C4）。
- 车体：vehicleController + 轮节点；角色：character controller 胶囊；布料：顶点质点弹簧。

### J 音频可视化

官方示例：`webaudio_visualizer`、`webaudio_timing`、`webaudio_orientation`

```js
const listener = new THREE.AudioListener();
camera.add(listener);
const audio = new THREE.Audio(listener);
audio.setMediaElementSource(mediaElement);
const analyser = new THREE.AudioAnalyser(audio, 128);
// 循环里：analyser.getFrequencyData(array) → 喂给柱状/粒子高度
```

- 浏览器自动播放策略：必须由**用户手势**启动（按钮点击里 init），不能页面一加载就 `play()`。
- 声场方位：`audio.setDirectionalCone(...)` + listener 朝向。
- 反馈层规范见 `20-sound-and-feedback.md`。

### K 视频与全景

官方示例：`webgl_video_panorama_equirectangular`

```js
const video = document.getElementById('video');
video.play();
const texture = new THREE.VideoTexture(video);
texture.colorSpace = THREE.SRGBColorSpace;
const geo = new THREE.SphereGeometry(5, 60, 40);
geo.scale(-1, 1, 1);                        // 翻到内表面
const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: texture }));
```

- 拖动转视角：记录 pointerdown 的 lon/lat，pointermove 改相机俯仰偏航。
- 视频资产必须随包或提供占位海报；离线时用程序化天空替代。

### L 导出

| 导出器 | 用途 | 边界 |
|---|---|---|
| `GLTFExporter` | 交回 DCC/引擎 | 材质可能不完整，先看节点 |
| `STLExporter` / `PLYExporter` | 3D 打印 / 点云 | 只导几何 |
| `OBJExporter` / `USDZExporter` | 通用交换 / AR | USDZ 带贴图限制 |
| `DRACOExporter` / `EXRExporter` / `KTX2Exporter` | 压缩几何 / 环境 / 纹理 | 需对应解码器 |

- **无头环境导不出**：没有 WebGL 上下文，几何和材质都构建不出来；导出按钮放页面内，用户点一下触发下载。

## 三、覆盖矩阵

| 能力 | 内置 vendor | 按需 addon | 文档模式 | 不支持 / 原因 |
|---|:--:|:--:|:--:|---|
| 轨道/地图/指针锁/飞行/变换/拖拽控件 | 部分 | ✅ | — | |
| Composer / Bloom / SSAO / LUT / Outline / Film | 部分 | ✅ | — | |
| GLTF/OBJ/STL/PLY/SVG/Font/RGBE 加载 | 部分 | ✅ | — | |
| DRACO / KTX2 / FBX 加载 | — | ✅ | — | 解码器/fflate 是运行时资产 |
| RoomEnvironment / Sky / Water / Reflector / Refractor / Lensflare | 部分 | ✅ | — | 光斑贴图按需 |
| Loft / Parametric / Convex / Decal / RoundedBox / Teapot | ✅ | — | — | |
| Line2 粗线 / MarchingCubes / ShadowMesh / Gyroscope | 部分 | ✅ | — | |
| SimplexNoise / ImprovedNoise / MeshSurfaceSampler / ConvexHull | 部分 | ✅ | — | |
| SelectionBox / Helper / InteractiveGroup / HTMLMesh | — | ✅ | — | |
| GPUComputationRenderer / CCDIKSolver / Helper | — | ✅ | — | |
| STL / PLY 导出 | — | ✅ | GLTF 已内 | OBJ/USDZ/DRACO/EXR/KTX2 按需 |
| 物理（Rapier/Ammo/Jolt） | — | ✅ | ✅ | WASM 不进离线包；离线用弹簧链 |
| WebGPU / TSL 节点材质 | — | — | ✅ | 默认交付 WebGL 兼容路径 |
| WebXR（VR/AR） | — | ✅ | ✅ | 需要头显与会话，不进默认演示 |
| 外部模型/音频/视频资产 | — | — | ✅ | 随包或占位，不在代码里伪造 |

## 四、反推时的取舍清单

拿到一个示例，先判它属于哪类，再决定抄什么：

1. **结构可抄**：场景搭建顺序、控件配置、pass 顺序、循环更新顺序。
2. **API 可抄**：构造参数、关键属性、更新调用。
3. **素材不抄**：模型路径、贴图、音频、字体、HDR——换成本任务的构件或程序化占位。
4. **运行时资产不内联**：WASM 解码器、压缩纹理 transcoder、外部字体；离线版明确降级。
5. **示例代码不直译**：示例常为单文件演示，变量挂全局；移植时按本技能构件树分包、加状态机与销毁逻辑。
