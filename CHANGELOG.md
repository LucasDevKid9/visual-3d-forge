# CHANGELOG

## v2.0.1 · 2026-11-17

修复 v2.0 的三处缺陷，不动整体框架。

### 修复

- **D1 离线单文件白屏（严重）**：`bundle.py` 遇到同一相对依赖被引用两次时（`three.module.js` 同时
  `import` 与 `export ... from './three.core.js'`），第二次仍自增编号，产出未注册的 `vf-int-2`，
  浏览器报 `Failed to resolve module specifier` 且页面全白。改为命中 `seen` 时复用已注册 specifier。
- **`--vendor` 死参数**：`main()` 未把 `args.vendor` 传给 `cmd_bundle`，骨架能跑只因 importmap 相对路径恰好指对；换布局会静默跳过全部模块。
- **自检盲区**：`--self-test` 只测单次相对依赖，恰好绕开上述缺陷。新增「同一依赖被 import 与 re-export 各一次」样本，并解码所有内联模块校验无悬空 `vf-int-N`。
- **校验器盲区**：`validate_scene.py` 的 D1 分支只验 importmap 是否 data URL，验不出悬空引用。新增 E16 悬空 specifier 检查（D1 模式，19 项）。

### 文档

- `SKILL.md`：`vendor.py --list` 示例补 `--three`（实现一直要求它）。
- `references/12-api-verification.md`：注明本包只含 build 产物，`api_lookup.py` 需另取 `npm pack three@0.187.0` 源码。

---

## v2.0 · 2026-11-17

从「单文件 CDN 一条路」升级为「双轨四档 + 四工具 + 三库」。核心变化是：**交付形态成为设计决策，而不是默认动作**。

### 新增能力

**四档交付形态（G4 依赖闸）**

| 档 | 产物 | 实测体积 | 依赖 |
|---|---|---|---|
| D0 | 单文件 CDN | 13 KB | 联网 |
| D1 | 单文件内嵌 three 全离线 | 2852 KB | 零 |
| D2 | HTML + vendor 目录 | 13 KB + 2391 KB | 零 |
| D3 | React Three Fiber 工程 | 标准工程 | 构建链 |

D1 与 D2 的 vendor 来自 three 0.187.0 官方包按 profile 裁剪，递归解析 addon 相对依赖闭包。

**四个工具**

- `vendor.py` — 依赖裁剪与离线化。profile 四档（core/standard/post/full），递归闭包（`RGBELoader` 自动带出 `HDRLoader`），输出 `manifest.json`（含 sha12）+ `importmap.json`。
- `bundle.py` — 单文件内嵌打包。把 importmap 每个模块转 data URL，**递归内联相对依赖闭包并改写为 `vf-int-N` bare specifier**（data URL 模块无目录概念，这一步漏了就白屏）。支持 `--vendor` 显式指定根目录。
- `api_lookup.py` — API 真实性查证。从 three 源码递归解析 export 链建符号表（488 项），`check` 扫描产物里所有 `THREE.X` 与 addon 路径做差集，`--strict` 时非零退出。
- `validate_scene.py` — 19 项静态自检。新增交付形态识别、三角面预算估算、R3F 反模式检测、API 真实性集成。

**三套库**

- `09-part-library.md` — 27 个可抄构件函数（基础形体/工业件/电子件/机械件/建筑件/自然件/抽象件），含面数量级标注。
- `10-material-recipes.md` — 材质数值配方表（金属 10 种、塑料 6 种、玻璃 2 种、陶瓷石材 6 种、有机 5 种、特殊 4 种）+ 4 个程序化贴图生成函数。
- `11-r3f-track.md` — R3F 语义、`useFrame` 三铁律、九类陷阱、资源生命周期、最小完整工程。

**两篇协议**

- `00-delivery-modes.md` — 四档形态矩阵、决策树、换档步骤、vendor profile。
- `12-api-verification.md` — API 查证铁律、三类高危错误对照表、11 条参数语义陷阱。

### 骨架

- `assets/scaffold/forged-scene.html` — D0（保留 v1 版本）
- `assets/scaffold/forged-scene.vendor.html` — D2 新增
- `assets/scaffold/r3f-app/` — D3 新增（Vite + React 19 + R3F 9，7 文件）
- `assets/vendor/` — 18 文件 2391 KB，可直接用

### 流程变化

- 五闸门（原四闸门 + G4 依赖闸）
- P3 加入强制 API 查证步骤
- 技术硬契约 10 条 → 12 条（新增形态一致性、数据贴图色彩空间）
- 质量红线新增「API 幻觉」

### 实测记录

```
vendor.py   --profile standard   → 18 文件 2391.0 KB（含自动带出的 HDRLoader）
bundle.py   13.3 KB 源           → 2851.5 KB 单文件，4 模块全内联，零远程引用
            three 643.5K / three.core 1440.2K / OrbitControls 40.0K / RoomEnvironment 4.8K
api_lookup  符号表 488 项        → scaffold 44 处引用全通过；负向样本正确抓到拼写错误
validate    D0/D1/D2 三档        → 各 19 通过 / 0 警告 / 0 失败
```

### 保留不变

v1 的 8 篇 references（01–08）、四角色契约、六阶段主流程、算法图谱、十条质量红线全部保留，未做破坏性改动。

---

## v1.0

从参考图到可运行单文件三维网页。四闸门、六阶段、算法图谱（A–F 六族 43 个算法）、12 项验收清单。
