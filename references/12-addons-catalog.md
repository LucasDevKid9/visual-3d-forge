# 12 · Addons 目录与依赖闭包

> three.js r187 的 `examples/jsm` 共 **506 个文件**。全部内置既臃肿又没必要。
> 本 Skill 已收录 **77 个** addon 文件（`assets/three/addons/`，已按依赖闭包复制），
> 编译进 `three.bundle.min.js` 供离线版使用；其余按需从完整包补齐，遵守本文**依赖闭包规则**。
> 官方示例反推出的模式与覆盖矩阵见 `23-official-examples-atlas.md`。

---

## 一、已内置清单

### controls（3）
| 文件 | 用途 | 关键 API |
|---|---|---|
| `controls/OrbitControls.js` | 轨道环绕，默认交互方案 | `enableDamping` `dampingFactor` `minDistance` `maxDistance` `minPolarAngle` `maxPolarAngle` `enablePan` `target` `autoRotate` |
| `controls/MapControls.js` | 地图式平移（左键拖平移） | 同 Orbit，交互映射不同 |
| `controls/PointerLockControls.js` | 第一人称视角 | `lock()` `unlock()` `moveForward()` `moveRight()` |

### environments（2）
| 文件 | 用途 |
|---|---|
| `environments/RoomEnvironment.js` | 程序化室内 IBL 环境，**无参构造**，产品展示首选 |
| `environments/ColorEnvironment.js` | 单色环境，适合纯色棚拍 |

### loaders（6）
| 文件 | 用途 |
|---|---|
| `loaders/GLTFLoader.js` | glTF/GLB 主模型格式 |
| `loaders/RGBELoader.js` | .hdr 环境贴图（配合 PMREMGenerator） |
| `loaders/HDRLoader.js` | HDR 的另一实现（RGBE 变体） |
| `loaders/OBJLoader.js` | OBJ 静态网格 |
| `loaders/SVGLoader.js` | SVG → Shape 路径，做拉伸/徽标 |
| `loaders/FontLoader.js` | typeface.json → TextGeometry |

### postprocessing（7）
| 文件 | 用途 |
|---|---|
| `postprocessing/EffectComposer.js` | 后处理管线容器 |
| `postprocessing/RenderPass.js` | 基础渲染 pass（必需） |
| `postprocessing/ShaderPass.js` | 自定义 shader pass |
| `postprocessing/MaskPass.js` | 遮罩 pass（Composer 依赖） |
| `postprocessing/UnrealBloomPass.js` | 泛光，做发光/科技感 |
| `postprocessing/OutputPass.js` | **色彩空间与色调映射收尾，必须放最后** |
| `postprocessing/Pass.js` | Pass 基类（Composer 依赖） |

### geometries（5）
| 文件 | 用途 |
|---|---|
| `geometries/ParametricGeometry.js` | 参数方程曲面（数学可视化） |
| `geometries/TeapotGeometry.js` | 犹他茶壶（经典测试模型） |
| `geometries/RoundedBoxGeometry.js` | 圆角盒（产品外壳首选） |
| `geometries/ConvexGeometry.js` | 点集凸包 |
| `geometries/DecalGeometry.js` | 贴花投影（Logo、划痕、标签） |

### objects（3）
| 文件 | 用途 |
|---|---|
| `objects/Sky.js` | 物理天空（大气散射） |
| `objects/Water.js` | 水面（反射 + 法线扰动） |
| `objects/Reflector.js` | 平面镜面反射（地面、展台） |

### math（2）
| 文件 | 用途 |
|---|---|
| `math/ConvexHull.js` | 凸包算法（ConvexGeometry 依赖） |
| `math/MeshSurfaceSampler.js` | 表面均匀采样（散布、粒子附着） |

### modifiers（2）
| 文件 | 用途 |
|---|---|
| `modifiers/TessellateModifier.js` | 细分（做形变前的加密） |
| `modifiers/SimplifyModifier.js` | 减面（性能优化） |

### utils（3）
| 文件 | 用途 |
|---|---|
| `utils/BufferGeometryUtils.js` | `mergeGeometries` `mergeVertices` `toTrianglesDrawMode` |
| `utils/SkeletonUtils.js` | 骨骼克隆（角色多实例） |
| `utils/SceneUtils.js` | 场景工具 |

### 其余（7）
| 文件 | 用途 |
|---|---|
| `helpers/ViewHelper.js` | 右下角轴向导航器 |
| `lights/RectAreaLightUniformsLib.js` | 面光源 LTC 查找表（用 RectAreaLight 必须 init） |
| `exporters/GLTFExporter.js` | 导出 glTF（导出当前场景） |
| `libs/lil-gui.module.min.js` | 参数调试面板（`GUI`） |
| `libs/stats.module.js` | FPS 面板（`Stats`） |
| `libs/meshopt_simplifier.module.js` | Meshopt 压缩解码 |
| `shaders/CopyShader.js` `shaders/LuminosityHighPassShader.js` `shaders/OutputShader.js` | Composer / Bloom 依赖的 shader |

### v3.2 对齐官方示例后新增内置

| 类别 | 文件 | 用途 |
|---|---|---|
| controls | `TransformControls` `DragControls` `FlyControls` | 拖拽变换 / 平面拖拽 / 自由飞行 |
| postprocessing | `SSAOPass` `LUTPass` `OutlinePass` `FilmPass` | 缝隙 AO / 调色 LUT / 选中描边 / 颗粒扫描线 |
| loaders | `STLLoader` `PLYLoader` `MeshoptDecoder` | 3D 打印网格 / 点云 / Meshopt 解码 |
| geometries | `LoftGeometry` | 截面链放样（车身、管材） |
| objects | `Refractor` `Lensflare` `LensflareElement` `MarchingCubes` `ShadowMesh` | 折射 / 镜头光斑 / 融球流体 / 软影接收 |
| math | `SimplexNoise` `ImprovedNoise` | 噪声地形、散布、扰动 |
| lines | `Line2` `LineGeometry` `LineMaterial` | 像素粗线（核心 Line 仅 1px） |
| interactive | `SelectionBox` `SelectionHelper` `InteractiveGroup` `HTMLMesh` | 框选 / 3D 内 DOM 标签 |
| misc | `GPUComputationRenderer` `Gyroscope` | GPGPU 双纹理模拟 / 跟随旋转刚体 |
| animation | `CCDIKSolver` `CCDIKHelper` | 反向运动学 |
| exporters | `STLExporter` `PLYExporter` | 打印网格 / 点云导出 |
| libs | `tween.module.js`（`TWEEN`） | 补间动画（缓动编排） |

---

## 二、常用但未内置（按需补齐）

从完整包 `examples/jsm/` 复制对应文件，**同时补齐依赖**：

| 文件 | 何时需要 |
|---|---|
| `loaders/DRACOLoader.js` | 压缩过的 glTF（需配 decoder 目录） |
| `loaders/KTX2Loader.js` | KTX2 压缩纹理（移动端省显存） |
| `loaders/EXRLoader.js` | .exr 环境贴图 |
| `loaders/FBXLoader.js` | FBX 模型（需 `libs/fflate.module.js`） |
| `postprocessing/SMAAPass.js` | 更高质量的边缘抗锯齿 |
| `postprocessing/GTAOPass.js` | 更快的 AO |
| `postprocessing/BokehPass.js` | 景深 |
| `postprocessing/HalftonePass.js` | 半调网点（印刷风） |
| `helpers/RectAreaLightHelper.js` | 面光源可视化调试 |

---

## 三、依赖闭包规则（补文件必读）

addon 之间用**相对路径**互相 import，只拷主文件会 404。

```bash
# 正确做法：连同依赖一起拷，保持目录结构
cp -r examples/jsm/postprocessing/{EffectComposer,RenderPass,ShaderPass,MaskPass,Pass}.js \
      examples/jsm/postprocessing/{UnrealBloomPass,OutputPass}.js \
      examples/jsm/shaders/{CopyShader,LuminosityHighPassShader,OutputShader}.js \
      <目标>/addons/
```

**已知依赖关系**

```
EffectComposer        → Pass, CopyShader, ShaderPass, MaskPass
UnrealBloomPass       → CopyShader, LuminosityHighPassShader, Pass
OutputPass            → Pass, OutputShader
ConvexGeometry        → ConvexHull
DecalGeometry         → (无)
GLTFLoader            → (无强制依赖；DRACO/KTX2/Meshopt 为可选插件)
FBXLoader             → libs/fflate.module.js
Water                 → (无，但需法线贴图)
Sky                   → (无)
RectAreaLight         → RectAreaLightUniformsLib.init()
```

**自动求闭包脚本**（本 Skill 已内置能力，可直接复用）：

```python
import os, re, shutil
pat = re.compile(r"""from\s+['"](\.[^'"]+)['"]""")
def closure(src, seeds):
    seen, q = set(), list(seeds)
    while q:
        rel = q.pop()
        if rel in seen or not os.path.exists(os.path.join(src, rel)): continue
        seen.add(rel)
        txt = open(os.path.join(src, rel), encoding='utf-8', errors='ignore').read()
        for m in pat.findall(txt):
            q.append(os.path.normpath(os.path.join(os.path.dirname(rel), m)))
    return seen
```

---

## 四、五个典型配方

### 1. 产品展示（最常用）

```js
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
// 三光 + 接触阴影 + OrbitControls 限位
```

### 2. 科技感发光

```js
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(w, h), 0.6, 0.4, 0.85);
composer.addPass(bloom);
composer.addPass(new OutputPass());   // 必须最后，负责 toneMapping + 色彩空间
// 渲染改 composer.render()
```

**注意**：开了 Composer 后，`renderer.toneMapping` 由 OutputPass 统一处理，
不要再手动转换一次（否则 E06/E07 会报双重转换）。

### 3. 天空与户外

```js
import { Sky } from 'three/addons/objects/Sky.js';
const sky = new Sky();
sky.scale.setScalar(450000);
sky.material.uniforms.turbidity.value = 8;
sky.material.uniforms.rayleigh.value = 2;
sky.material.uniforms.mieCoefficient.value = 0.005;
sky.material.uniforms.sunPosition.value.copy(sunDir);
```

### 4. 地面反射展台

```js
import { Reflector } from 'three/addons/objects/Reflector.js';
const mirror = new Reflector(new THREE.PlaneGeometry(20, 20), {
  clipBias: 0.003,
  textureWidth: 1024,
  textureHeight: 1024,
  color: 0x8899aa
});
mirror.rotateX(-Math.PI / 2);
```

### 5. 表面散布（草地、粉尘、星点）

```js
import { MeshSurfaceSampler } from 'three/addons/math/MeshSurfaceSampler.js';
const sampler = new MeshSurfaceSampler(surfaceMesh).build();
const dummy = new THREE.Object3D();
for (let i = 0; i < 2000; i++) {
  sampler.sample(pos, normal);
  dummy.position.copy(pos);
  dummy.lookAt(pos.clone().add(normal));
  dummy.updateMatrix();
  inst.setMatrixAt(i, dummy.matrix);
}
```

---

## 五、addon 使用红线

1. **不要在 standalone 模式下 import addon** —— bundle 已内置 64 个，用 `window.THREE_BUNDLE.XXX` 解构。
2. **不要混用 `three/examples/jsm/` 和 `three/addons/`** —— 统一后者。
3. **RectAreaLight 必须 `RectAreaLightUniformsLib.init()`**，否则面光源不发光。
4. **Composer 的 OutputPass 必须是最后一个 pass**，否则色彩管线错位。
5. **`renderer.info.render.calls` 是性能第一指标**，超过预算先查是否该用 InstancedMesh。
