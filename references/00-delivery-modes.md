# 00 · 交付形态与依赖策略

> 在写第一行几何代码之前，先回答一个问题：**这份东西要在哪里被打开？**
> 三维交付最常见的翻车不是画面不好看，而是"在你这能跑，在客户那打不开"。

---

## 一、四档形态

| 档 | 形态 | 运行时依赖 | 实测体积 | 断网 | 交付方式 | 适用场景 |
|---|---|---|---|---|---|---|
| **D0** | 单文件 + CDN | 需要联网 | 50–200 KB | ✗ | 单个 .html | 演示、评审、快速验证、发给能上网的人 |
| **D1** | 单文件 + 内嵌 vendor | **零** | 2.8–4 MB | ✓ | 单个 .html | 邮件附件、内网、断网机器、归档留证 |
| **D2** | HTML + vendor 目录 | **零** | 同上，但分散 | ✓ | 一个文件夹 | 长期维护、多人协作、反复迭代 |
| **D3** | R3F 工程 | npm 构建 | 产物 1–3 MB | ✓ | 仓库 / 构建产物 | 组件化、状态管理、复杂交互、团队开发 |

体积数据来自本 Skill 自带的 `assets/vendor`（three 0.187.0 核心 + OrbitControls + RoomEnvironment + CSS2DRenderer）经 `bundle.py` 实测：13.3 KB 源文件 → 2851.5 KB 单文件。

---

## 二、决策树

按顺序问，第一个"是"就定档：

```
1. 需要组件复用 / 全局状态 / 多人长期迭代？
   → 是 → D3（见 11-r3f-track.md）

2. 交付对象可能断网、在内网、或需要邮件发送 / 归档留证？
   → 是 → 3

3. 能接受交付一个文件夹（对方会整体拷贝）？
   → 是 → D2
   → 否 → D1

4. 以上都不是：对方能上网，只是要看效果
   → D0
```

**默认建议**：不确定时选 **D1**。多花的 2.8MB 换掉的是"打不开"这一类最丢人的失败。

---

## 三、各档硬约束

### D0 · 单文件 CDN

- **版本必须锁死**：`three@0.187.0`，不许写 `three@latest` 或 `three`。上游一次 breaking change 就能让你的页面永久损坏。
- **CDN 白名单**：`fastly.jsdelivr.net` 优先。**禁用** `unpkg.com`、`bootcdn`、`staticfile.org`、`polyfill.io`、`cdn.bootcss`（供应链投毒与失效风险）。
- **必须做能力兜底**：CDN 挂了要给用户一句人话，不能白屏。

```html
<script type="importmap">
{"imports":{
  "three":"https://fastly.jsdelivr.net/npm/three@0.187.0/build/three.module.js",
  "three/addons/":"https://fastly.jsdelivr.net/npm/three@0.187.0/examples/jsm/"
}}
</script>
```

### D1 · 单文件内嵌

- 由 `bundle.py` 生成，**不许手工编辑产物的 importmap**。
- 相对依赖必须递归内联。`three.module.js` 内部 `import ... from './three.core.js'`，而 data URL 模块没有目录概念——漏掉 `three.core.js` 就是白屏 + `Failed to resolve module specifier`。
- 生成后必须验证"无剩余远程引用"（`bundle.py` 会打印）。
- 体积超过 4MB 时评估是否改用 D2。

```bash
python3 scripts/bundle.py --src scene.html --out scene.offline.html --vendor <vendor根> --report
python3 scripts/validate_scene.py scene.offline.html
```

### D2 · 本地 vendor 目录

- `vendor/` 必须**整体交付**，含 `manifest.json`；少一个文件即失效。
- importmap 用相对路径，`vendor/` 与 HTML 的相对位置不能变。
- 交付前跑 `vendor.py --self-test` 核对文件完整性。

```html
<script type="importmap">
{"imports":{
  "three":"../vendor/three.module.js",
  "three/addons/":"../vendor/addons/"
}}
</script>
```

### D3 · R3F 工程

- `react >=19 <19.4`、`@react-three/fiber 9.x`、`three 0.187.x`。
- 三条反模式铁律见 `11-r3f-track.md`；`validate_scene.py` 会自动扫 `useFrame` 内 setState。

---

## 四、工具链

四个脚本，都只用 Python 标准库。

```bash
# 1. 从完整发行包裁剪最小 vendor 集（自动递归解析 addon 相对 import）
python3 scripts/vendor.py --three <three包根> --out assets/vendor --profile standard
python3 scripts/vendor.py --three <three包根> --list          # 看看有哪些 addon 可用

# 2. 把 vendor 内联成单文件（含相对依赖闭包）
python3 scripts/bundle.py --src scene.html --out scene.offline.html --vendor <vendor根> --report

# 3. 写完代码立刻核对 API 是否真实存在
python3 scripts/api_lookup.py check scene.html --three <three包根>
python3 scripts/api_lookup.py find MeshPhysicalMaterial --three <three包根>   # 查签名

# 4. 交付前自检（含 API 真实性、面数预算、光照契约）
python3 scripts/validate_scene.py scene.html --three <three包根>
```

`vendor.py` 的 profile：

| profile | 内容 | 体积 |
|---|---|---|
| `core` | OrbitControls / CSS2DRenderer / RoomEnvironment / BufferGeometryUtils | ≈2.4 MB |
| `standard` | core + MapControls / TrackballControls / GLTFLoader / RGBELoader / Line2 系 / SkeletonUtils | ≈2.4 MB |
| `post` | EffectComposer / RenderPass / ShaderPass / UnrealBloomPass / OutputPass / SMAAPass | 按需 |
| `full` | standard + post + EXR / Draco / KTX2 / Convex / RoundedBox 等 | ≈3 MB |

> `DRACOLoader` / `KTX2Loader` 依赖外部 wasm 解码器，脚本只复制调用代码，`manifest.json` 里标记 `external: true`。用到时必须另行部署解码器并 `setDecoderPath()`，否则模型加载失败。

---

## 五、换档时机与步骤

### D0 → D1（客户要离线）

```bash
# 1. 把 CDN 版 importmap 换成 vendor 相对路径
#    three  → ../vendor/three.module.js
#    three/addons/ → ../vendor/addons/
# 2. 内联
python3 scripts/bundle.py --src scene.html --out scene.offline.html --vendor <vendor根>
```

### D1 → D2（要开始长期改）

反向操作：把 importmap 从 data URL 换回 `../vendor/` 路径。内联产物不适合继续编辑。

### D2 → D3（要上 React 应用）

不是简单转换。几何/材质/光照逻辑可以搬，但**渲染循环、状态、生命周期要按 R3F 语义重写**（`useFrame` / `useMemo` / `dispose`）。参见 `11-r3f-track.md`。

---

## 六、自检清单

- [ ] 形态已明确，且与交付场景匹配（不是"顺手用了 CDN"）
- [ ] D0：版本锁死、CDN 在白名单、有加载失败提示
- [ ] D1：`bundle.py` 生成、无剩余远程引用、体积已记录
- [ ] D2：`vendor/` 完整、`manifest.json` 存在、相对路径正确
- [ ] D3：依赖版本符合区间、无反模式（`useFrame` 内 setState）
- [ ] 无论哪档，`validate_scene.py` 无 FAIL
