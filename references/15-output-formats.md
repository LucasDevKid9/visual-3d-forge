# 15 · 产出形态：不止 HTML

## 先分清三件事

一个三维交付物有三个彼此独立的维度，混在一起谈就会得出「只能出 HTML」的错误结论：

| 维度 | 问题 | 决定因素 |
|---|---|---|
| **载体（runtime）** | 它靠什么跑起来 | WebGL / Canvas2D / 纯静态 / 视频帧 |
| **容器（container）** | 它被打包成几个什么文件 | 单文件 / 目录 / 归档 |
| **可编辑性** | 别人能不能接着改 | 源码可读 / 已压缩 / 已栅格化 |

HTML 只是**容器**的一种。换容器不改变载体，也不改变内容。

## 形态矩阵

| 形态 | 能跑 | 单文件 | 离线 | 体积 | 适用 |
|---|---|---|---|---|---|
| **standalone HTML** | ✅ | ✅ | ✅ | 0.8–2 MB | **默认交付**。双击即开，无需服务器 |
| **CDN HTML** | ✅（需联网） | ✅ | ❌ | 5–30 KB | 分享链接、体积敏感、可联网环境 |
| **local HTML + 资源目录** | ✅ | ❌ | ✅ | 3–8 MB | 需要替换素材、二次开发 |
| **MHT / MHTML** | ❌（脚本不执行） | ✅ | ✅ | 同内容 + 图 | **归档、邮件附件、文档系统留档** |
| **ZIP 工程包** | ✅（解压后） | ✅ | ✅ | 同内容 | 交付源码、多人协作、版本管理 |
| **GLB / GLTF** | —（模型） | ✅ | ✅ | 0.1–20 MB | 只要模型，交给 Blender/Unity/其他引擎 |
| **PDF 图纸** | —（静态） | ✅ | ✅ | 0.2–5 MB | 三视图、爆炸图、装配说明、打印 |
| **MP4 / GIF** | —（录像） | ✅ | ✅ | 1–50 MB | 汇报、社媒、无法运行 WebGL 的场合 |

> 「能跑」= 打开后场景可交互渲染，不是「能看到一张图」。

## MHTML 到底是什么

MHTML（RFC 2557）是 **MIME multipart 归档**：把 HTML 和资源塞进一个文件，每个资源一个 part，靠 `Content-Location` / `Content-ID` 互相引用。由浏览器「另存为 → 单个文件」生成。

**它是存档，不是应用格式。** 完整解剖、反推 SOP 与自建规则见 `22-web-archive-intake.md`。

### 实测结论（Linux Chromium，断网）

| 检验 | 结果 |
|---|---|
| 能否打开 | ✅ 标题 / 样式 / SVG / 内嵌图全部正常 |
| 普通 `<script>` | ❌ 不执行 |
| `<script type="module">` | ❌ 不执行 |
| 页面表现 | 停在首帧外壳（有启动遮罩就卡在遮罩上） |

跨浏览器：Edge / Windows 系原生支持；Chrome 各平台支持度不一；Safari 不支持；Firefox 需扩展。
**不要承诺「MHT 打开能跑」**，除非已在目标阅读器实测。

### 三个由此推出的规则

1. **MHT 只承担「长什么样」，承担不了「能跑」。** 要跑 → standalone HTML。
2. **别为 MHT 做「importmap 兼容」这种无用功。** 脚本根本不执行，模块能不能解析都不重要。
3. **要让归档有意义，必须预烘首帧。** 否则收件人只打开一张空壳。

## 三种成色的 MHT

| 成色 | 内容 | 打开后 |
|---|---|---|
| A 可运行（少数环境） | 自包含 HTML，无 import、无外部资源 | 在允许脚本的阅读器里可玩，多数环境降级成 B |
| **B 可读档案（默认目标）** | 预烘首帧 PNG + 规格文字 + 玩法三行 + 运行版指引 | 任何浏览器都能读到「是什么、长什么样、怎么玩真的」 |
| C 仅源码（最差） | 只有 HTML 文本，资源没内联 | 图裂、样式丢，等于把源码当附件 |

### B 档配方（四件套）

1. **首帧**：无头浏览器截一张稳定帧（1280×720），压到 < 300 KB；
2. **规格卡**：对象名、关键参数、构件数；
3. **玩法三行**：键盘 / 鼠标 / 触控各一句；
4. **落地指引**：一句「可运行版为同名 standalone HTML」。

```bash
# 1) 先出可运行版（真交付）
python3 scripts/build_standalone.py ./out/index.html -o ./out/scene.html
# 2) 截图得到 shot.png（无头截图配方见 14-offline-and-assets.md）
# 3) 打成档案版（首帧 + cid 重写 + 回读校验）
python3 scripts/export_mht.py ./out/scene.html -o ./out/scene.mht \
    --poster ./out/shot.png --caption "首帧：雨中整车视图" --verify
```

## 本 Skill 的产出路由

```
用户要什么？
├─ 打开就能玩/看                 → standalone HTML（默认）
├─ 发链接、体积越小越好           → CDN HTML
├─ 我要改素材、接着开发           → local HTML + 资源目录（forge_init --mode local）
├─ 单个文件留档 / 发邮件 / 进 OA  → MHT 档案版（export_mht.py --poster）
├─ 打包带走全部源码               → ZIP
├─ 只要 3D 模型                  → 页面内 GLTFExporter 导 GLB
└─ 打印 / 汇报                    → PDF 图纸 或 MP4 录屏
```

**用户只说「一个文件」时，先分清意图**：要能玩 → HTML；要能发 → MHT + 首帧。

## 扩展其他形态的做法

**GLB**：页面里挂导出按钮，点一下得到模型。不要试图在无头环境导出——没有 WebGL 上下文，几何与材质都构建不出来。

```js
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
new GLTFExporter().parse(subject, (buf) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([buf], { type: 'model/gltf-binary' }));
  a.download = 'model.glb';
  a.click();
}, (e) => console.error(e), { binary: true });
```

**PDF 图纸**：不要截 3D 视口（透视会失真）。用 `OrthographicCamera` 分别渲三视图，导出 PNG 再排版。尺寸标注必须来自几何参数，不能目测。

**MP4**：用 `canvas.captureStream()` + `MediaRecorder` 在页面内录，帧率锁 30，录制期间固定 `dt`，否则回放速度会漂。

## 一个反直觉的结论

**standalone HTML 比 MHT 更「单文件」。**

- standalone：1 个文件，内部零外部引用，任何浏览器双击可跑；
- MHT：1 个文件，内部是多个 part，多数阅读器不放脚本。

所以「想要一个文件」的默认答案是 standalone HTML。
MHT 的价值只在「必须塞进只认 MIME 归档的系统」——那时用 B 档档案版，别用 C 档。
