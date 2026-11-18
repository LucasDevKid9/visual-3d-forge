# 13 · API 查证协议

> 三维代码最致命的失败不是逻辑错，是**编造 API**。
> `THREE.CapsuleGeomtry` 少一个 e，页面就是白屏 + 一行红字，而且静态检查完全看不出来。
> 你手边有 21MB 源码，没有任何理由靠记忆写符号名。
>
> ⚠️ 本包只随附 `assets/vendor/` 的 **build 产物**（`three.module.js` / `three.core.js`），
> 不含 `src/` 与 `examples/jsm/`，因此 `api_lookup.py` / `validate_scene.py --three` 开箱即报
> "找不到源码结构"。查证前先取一份源码：
> `npm pack three@0.187.0 && tar -xzf three-0.187.0.tgz`，再把 `--three package` 指过去。

---

## 一、铁律

**写任何 `THREE.X` 之前，如果不确定，先查。**

不是"大概记得"，不是"应该是"，是查。查的成本是 1 秒，猜的成本是交付后返工。

三个必查时刻：

1. 第一次用某个类/方法时
2. 构造参数超过 2 个时（顺序记错就是静默错位，画面诡异但不报错）
3. 写 addon 路径时（目录名几乎没人记得准）

---

## 二、三类高危错误

### 1. 拼写错误

模型对符号名的"感觉"是统计出来的，不是查出来的，所以会产出看起来很像的假名字。

| 编造的 | 真实的 |
|---|---|
| `THREE.CapsuleGeomtry` | `THREE.CapsuleGeometry` |
| `THREE.MeshPhysicalMateral` | `THREE.MeshPhysicalMaterial` |
| `material.clearCoatRoughness` | `material.clearcoatRoughness`（小写 c） |
| `THREE.PMREMGenarator` | `THREE.PMREMGenerator` |
| `THREE.WebGLRenderTarget` 用成 `THREE.RenderTarget` | 无 `RenderTarget` 类 |

### 2. 签名错误

```js
// 错：以为 TorusGeometry(radius, tube, radialSeg, tubularSeg)
new THREE.TorusGeometry(1, 0.4, 12, 48)   // 实际是 (radius, tube, radialSegments, tubularSegments) ✓

// 错：LatheGeometry 参数顺序记反
new THREE.LatheGeometry(32, points)        // 实际是 (points, segments, phiStart, phiLength)

// 错：ExtrudeGeometry 直接传对象却漏了 steps
new THREE.ExtrudeGeometry(shape, { depth: 1 })   // 可跑，但倒角/步数默认值常不符合预期
```

### 3. 路径错误

addon 的真实目录是按功能分的，不是全平铺：

| 常见写法 | 实际路径 |
|---|---|
| `three/addons/OrbitControls.js` | `three/addons/controls/OrbitControls.js` |
| `three/addons/CSS2DRenderer.js` | `three/addons/renderers/CSS2DRenderer.js` |
| `three/addons/RoomEnvironment.js` | `three/addons/environments/RoomEnvironment.js` |
| `three/addons/GLTFLoader.js` | `three/addons/loaders/GLTFLoader.js` |
| `three/addons/EffectComposer.js` | `three/addons/postprocessing/EffectComposer.js` |
| `three/addons/BufferGeometryUtils.js` | `three/addons/utils/BufferGeometryUtils.js` |

---

## 三、查证流程

### 查一个符号定义在哪、怎么写的

```bash
python3 scripts/api_lookup.py find MeshPhysicalMaterial --three <three包根>
```

```
MeshPhysicalMaterial  →  src/materials/MeshPhysicalMaterial.js:37
    class MeshPhysicalMaterial extends MeshStandardMaterial {
    constructor( parameters ) {
```

拿到文件名和行号，需要细节就去看那几行源码。**这比任何文档都权威**，因为文档可能滞后于版本。

### 列出全部导出符号

```bash
python3 scripts/api_lookup.py list --three <three包根>
python3 scripts/api_lookup.py list --filter Geometry --three <three包根>
```

写代码前扫一眼，比凭记忆强。

### 批量校验一个文件

```bash
python3 scripts/api_lookup.py check scene.html --three <three包根>
python3 scripts/api_lookup.py check scene.html --three <three包根> --strict
```

输出：

```
[api] three.js 0.187.0 · 符号表 488 项 · 检查 scene.html
[api] 共核对 256 处引用
[api] 可疑 2 处：
  行     1  CapsuleGeomtry；是否想用 CapsuleGeometry / ShapeGeometry / CircleGeometry
  行     4  addons/OrbitControl.js；该 addon 不存在
```

`--strict` 让 CI 在发现可疑时返回非零。

### 缓存说明

首次建表约 10–20 秒（要读几百个源文件），结果缓存在 `scripts/.cache/`，之后每次 <2 秒。升级 three 版本或想强制重建时加 `--refresh`。

---

## 四、参数语义陷阱

这些不是拼写问题，是**语义理解错**，错了能跑但效果不对。

| 陷阱 | 说明 |
|---|---|
| `setPixelRatio` vs `window.devicePixelRatio` | 后者是物理值不可改，前者是你主动设的上限。必须 `Math.min(devicePixelRatio, 2)` |
| `toneMapping` 与 `outputColorSpace` 顺序 | 两者都只在初始化设一次。重复赋值 = 双重转换 = 画面发灰 |
| `color.set()` vs `color.setHex()` | 前者走色彩空间转换，后者直接写值。从设计稿取色用 `set('#ff0000')` |
| `texture.colorSpace` | 只有**颜色贴图**（map / emissiveMap）设 `SRGBColorSpace`；法线、粗糙度、AO 贴图**不能设**，否则数据被当颜色转换，材质会错 |
| `InstancedMesh` 更新 | 改完 `setMatrixAt` 必须 `instanceMatrix.needsUpdate = true`，否则毫无变化 |
| `CSS2DRenderer.setSize` | 必须与 `WebGLRenderer.setSize` 用同一组尺寸，否则标签错位 |
| `geometry.dispose()` vs `material.dispose()` | 两者都要，且 `material.dispose()` 不会释放贴图，贴图要单独 dispose |
| `transparent` 运行期切换 | 改 `material.transparent` 会触发 shader 重编译，卡顿明显。初始化时定死 |
| `fov` 默认 50 | 库默认值等于没选镜头。产品级用 32–45，广角空间用 55–70 |
| `directionalLight.shadow.camera` | 只设 `shadowMap.enabled` 不调 shadow camera 范围，阴影要么糊要么缺失 |
| `OrbitControls` 的 `target` | 改了 target 必须 `controls.update()`，否则下一帧才生效且可能与阻尼打架 |

---

## 五、集成到工作流

```
P3 算法装配：确定要用哪些类 → 先 --list --grep 确认存在
P4 代码实现：边写边查，第一次用的符号立即 --find
P4 收尾：   --check 全量核对，修掉所有可疑
P5 验收：   api_lookup.py check 查符号 → validate_scene.py --three <包根> 做最终把关
```

---

## 六、不确定时怎么办

1. **先查源码**（`--find`），源码是唯一真相。
2. 源码里没有 → 这个 API 不存在，换方案，不要"试试看"。
3. 源码里存在但你不确定怎么用 → 读它的 `constructor` 和同目录下的示例（`examples/` 里有 500+ 真实用法）。
4. 仍然不确定 → 在交付说明里写明"该处依赖 X 行为，未在真机验证"，不要假装确定。

---

## 七、自检清单

- [ ] 所有 `THREE.X` 都通过了 `--check`
- [ ] 所有 `three/addons/` 路径都带正确子目录
- [ ] 构造参数 ≥3 个的类，都确认过顺序
- [ ] 材质相关：`colorSpace` 只设在颜色贴图上
- [ ] 运行期不改 `material.transparent`
- [ ] `InstancedMesh` 更新后有 `needsUpdate`
