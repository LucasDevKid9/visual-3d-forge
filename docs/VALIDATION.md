# 验证记录

本文记录**实际跑出来的结果**，不是"应该能跑"。所有命令都在仓库根目录执行，
环境为 Linux + Python 3.11，three.js 0.187.0（`assets/vendor/`），
浏览器验证用 Chromium + SwiftShader（无 GPU 的软件光栅）。

---

## 一、测试套件

```bash
$ python3 -m pytest tests/ -q
69 passed in 0.95s
```

三个文件，各守一段承诺：

| 文件 | 用例 | 守的是什么 |
|---|---:|---|
| `test_contract.py` | 26 | 文档 ↔ 文件一致、vendor 哈希、四个脚本行为、D0/D2→D1 端到端、反向用例 |
| `test_playground.py` | 22 | 实验台的 importmap 逐条落地、求解器三条判据在场、SVG 无脚本、GIF 真是动图 |
| `test_links.py` | 21 | 每篇文档的相对链接、workflow 可解析且引用的脚本存在、门面文件齐全 |

### 反向用例清单（最重要的部分）

只测「对的时候对」的测试等于没测。以下用例**故意把东西弄坏**，断言它必须变红：

| 用例 | 破坏方式 | 期望 |
|---|---|---|
| 删 importmap | 从 D0 骨架里移除 `<script type="importmap">` | 默认模式只告警（退出码 0），`--strict` 必须失败 |
| 删 import 语句 | 移除 `import * as THREE` | 校验器必须报「模块脚本未导入 three」 |
| 悬空 specifier | 手工制造 `vf-int-9` 引用 | D1 模式 E16 必须失败（v2.0 白屏事故的回归） |
| 断链 | 文档里指向不存在的文件 | `test_links.py` 必须失败 |
| 静态图冒充动图 | GIF 帧数 < 40 | 必须失败 |
| 混入脚本的 SVG | `<script>` 出现在 banner 里 | 必须失败（GitHub 会清洗，等于白写） |

---

## 二、骨架自检（D0 / D2）

```bash
$ python3 scripts/validate_scene.py assets/scaffold/forged-scene.html
  结果：18 通过 / 0 警告 / 0 失败

$ python3 scripts/validate_scene.py assets/scaffold/forged-scene.vendor.html
  结果：18 通过 / 0 警告 / 0 失败
```

18 项里包含：单文件自包含、存在 module 脚本、three 版本锁定、未用禁用 CDN、像素比封顶、
toneMapping 单次、resize 处理、后台暂停、相机限位、fov 合理、WebGL 探测、渲染循环、
帧间隔钳制、三光结构、实时阴影、实例化、三角面预算、体积。

---

## 三、打包链路（D2 → D1）

```bash
$ python3 scripts/bundle.py --src assets/scaffold/forged-scene.vendor.html \
    --out /tmp/d1.html --vendor assets/vendor
[bundle] 内联 4 个模块（含相对依赖闭包）→ /tmp/d1.html
[bundle] 体积 13.3 KB → 2851.5 KB
[bundle] 无剩余远程引用，可断网运行

$ python3 scripts/validate_scene.py /tmp/d1.html
  结果：19 通过 / 0 警告 / 0 失败
```

19 项比 D0 多一项 **E16：内联闭包无悬空 specifier**——即每个 `vf-int-N` 都已注册。
这一项正是 v2.0 白屏事故之后补的（见 [`CHANGELOG.md`](../CHANGELOG.md) v2.0.1）。

外部引用扫描：

```bash
$ grep -oE "https?://[^\"' ]+" /tmp/d1.html | sort -u | wc -l
0
```

---

## 四、示例（行星齿轮减速器）

```bash
$ python3 scripts/validate_scene.py "examples/planetary-gear-3d/行星齿轮减速器.html" --strict
  · 交付形态：D0 单文件 CDN
  · 估算三角面：≈1,450
  · 体积：19 KB
  结果：18 通过 / 0 警告 / 0 失败
```

体积 19,132 字节。同一份源码经 `bundle.py` 可升到 D1（约 2.87 MB），本仓库不提交该产物
（`.gitignore` 已排除 `out/`、`dist/`、`*.tmp.html`）。

### 这次示例暴露的两个真实缺陷（保留记录）

1. **构件树切分错误**：行星架把上下压板放进同一个 group，爆炸时下压板随整体上移，
   反而重新盖住齿轮。修法是把下压板从构件树里去掉，让销轴下探代替它。
2. **径向位移不足**：行星轮只沿 Y 抬升，中心距仍是 39 mm，21 mm 半径 → 外缘 60 mm，
   正好插进齿圈内壁。修法是把 0.055 的径向系数提到 0.090，越过外壁 70 mm。

这两条都符合 [`DESIGN-NOTES.md`](DESIGN-NOTES.md) 第 6 条的规律：**看起来对 ≠ 跑得起来 ≠ 结构正确**。
校验器能抓 API 幻觉与白屏，抓不到"零件插进另一个零件"——那要靠人眼看，或靠包围盒自检。
本仓库目前只能靠人眼，这是 [`ARCHITECTURE.md`](ARCHITECTURE.md) 第八节承认的边界之一。

---

## 五、在线实验台（playground）

实验台是唯一「零安装即可验证」的部分，所以它被单独测了一遍——用真实浏览器跑，不是读代码。

### 5.1 逐帧录制管线

`playground/index.html` 带三个查询参数，构成一条可重复的录制通道：

| 参数 | 作用 |
|---|---|
| `?demo=1` | 展厅模式：相机缓慢绕轴 + 爆炸往复，齿轮按威利斯方程联动 |
| `?bare=1` | 隐藏全部 UI，只剩 canvas |
| `?still=1` | 停掉 rAF，改为 `window.__seek(t)` 逐帧驱动 |

`__seek(t)` 与实时渲染**共用同一个 `setPose()`**，所以录出来的每一帧都是这条渲染路径的真实输出，
不存在"为录制特调"的分支。

```bash
# 15 fps × 6.6 s = 99 帧，960×600
$ xvfb-run -a python3 tools/record_demo.py
$ ffmpeg -framerate 15 -i /tmp/frames/f%03d.png \
    -vf "fps=12,scale=760:-1,split[a][b];[a]palettegen=max_colors=112[p];[b][p]paletteuse=dither=bayer:bayer_scale=5" \
    -loop 0 docs/assets/demo.gif
```

产物：`docs/assets/demo.gif`，760×475，79 帧，2.92 MB。

### 5.2 交互实测

| 场景 | 操作 | 实测结果 |
|---|---|---|
| 合法参数 | `z₁=18, z₃=60` | `SOLVED`，i=4.33，z₂=21，a=39.0，εα=1.55 |
| 违反装配条件 | 拖 `z₃` 到 62 | `BLOCKED`，提示「80 ÷ 3 余 2」，几何停在上一状态，出现「按约束修正 → z₃ = 60」 |
| 点修正 | 点击按钮 | 回到 `SOLVED`，滑块与场景同步为 60 |
| 违反同心条件 | `z₁=18, z₃=61` | `BLOCKED`，提示 z₂ 非整数 |
| 邻接干涉 | `z₁=12, z₃=30`（z₂=9） | 通过（9 < (12+9)·sin60° − 2 ≈ 16.2），符合预期 |

### 5.3 视觉迭代中被修掉的真实缺陷

这些不是"调参"，是渲染逻辑错误，每一条都记录了判据：

| 缺陷 | 判据 | 修法 |
|---|---|---|
| 模型几乎不可见 | 单位混乱：求解用 mm、世界用 m，模型被放大 70 倍后落在相机 `far` 外 | `build()` 内 `m = s.m * 0.001`，其余全部派生 |
| 承影面掉到 −10 m | 爆炸位移公式里混用了 mm 的 `spec.m` | 位移统一以 `g.h`（米）为单位 |
| 行星轮压进齿圈壁 | 径向让位 `(ringOut−centerR)·k` 必然越界 | 改为纯轴向爆炸，径向不动 |
| 材质顶面纯白 | 环境贴图是均匀白顶棚，金属顶面镜面反射成一片 | 环境强度 0.58 + 粗糙度 0.52 + 机加工粗糙度贴图 |
| 任一爆炸度都会出框 | 相机只按当前 bbox 拟合 | 取「闭合态 ∪ 展开态」联合包围盒定框 |
| `PCFSoftShadowMap` 警告 | three r187 已移除该类型 | 改用 `PCFShadowMap` |

### 5.4 线上部署踩到的第一个坑：import map 的 URL-like 规则

**现象**：本地 `http://localhost/playground/` 一切正常，部署到 Pages 后整页只剩 UI，
控制台只有一句：

```
Failed to resolve module specifier "three".
Import Map: "three" matches with "three" but is blocked by a null value
```

网络面板里**一个 vendor 请求都没有**——不是 404，是根本没发起。

**根因**：Pages 部署时把 `index.html` 提到站点根，于是 `../assets/` 需要改写。
第一次改写成了 `assets/vendor/three.module.js`。这在文件系统语义下完全正确，
但 import map 的地址必须是 **URL-like**：只能以 `./`、`../`、`/` 或绝对 URL 开头。
`assets/...` 不满足，Chromium 判定该条目解析失败并置为 `null`，
于是整个映射表里 `three` 指向空，所有 import 都被拒绝。

**修法**：改写成 `./assets/vendor/three.module.js`。一个字，`./`。

**为什么没有更早发现**：本地的 importmap 用的是 `../assets/`（合法），
线上才变成裸相对路径——两边不同构，本地怎么测都测不出来。

**现在的防线**：`pages.yml` 在组装后用 Python 读一遍 import map，
逐条断言地址是 URL-like；`tests/test_playground.py` 里也钉了同一条断言。

### 5.5 齿形是近似，这点必须说清楚

轮齿用 `BoxGeometry` 实例化摆放（切向 1.55m、径向 2.0m，按模数派生），**不是渐开线**。
真值部分：齿数、分度圆、节圆相切、中心距、传动比、行星轮角速度关系。
非真值部分：齿廓曲线、重合度的精确值（按标准齿顶高系数 1.0 估算，未计入变位）。

写在这里，是为了避免"看起来像"被读成"算得准"。

---

## 六、未验证的部分（不粉饰）

| 项 | 状态 | 原因 |
|---|---|---|
| `api_lookup.py` 完整链路 | **未验证** | 需要 three 源码（`npm pack three@0.187.0`），本包只含 build 产物；缺源码时脚本给可读错误并有测试覆盖该路径 |
| 真实浏览器多设备兼容 | 未验证 | 仅在 Chromium + SwiftShader 下渲染截图；Safari / Firefox / 移动端未测 |
| 视觉质量 | 未量化 | 无参考图与渲染结果的像素比对 |
| `vendor.py` 重新裁剪 | 仅自检 | `--self-test` 校验目录结构；未对 npm 源码重跑 |
| D3（R3F）工程 | 未验证 | 只提供骨架，未执行 `npm i` / `vite build` |
| GitHub Pages 部署 | 未验证 | workflow 已就绪，首次推送后需人工确认站点可达 |
