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
| **standalone HTML** | ✅ | ✅ | ✅ | 0.6–2 MB | **默认交付**。双击即开，无需服务器 |
| **CDN HTML** | ✅（需联网） | ✅ | ❌ | 5–30 KB | 分享链接、体积敏感、可联网环境 |
| **local HTML + 资源目录** | ✅ | ❌ | ✅ | 3–8 MB | 需要替换素材、二次开发 |
| **MHT / MHTML** | ⚠️ 视浏览器 | ✅ | ✅ | 同内容 | **归档、邮件附件、文档系统留档** |
| **ZIP 工程包** | ✅（解压后） | ✅ | ✅ | 同内容 | 交付源码、多人协作、版本管理 |
| **GLB / GLTF** | —（模型） | ✅ | ✅ | 0.1–20 MB | 只要模型，交给 Blender/Unity/其他引擎 |
| **PDF 图纸** | —（静态） | ✅ | ✅ | 0.2–5 MB | 三视图、爆炸图、装配说明、打印 |
| **MP4 / GIF** | —（录像） | ✅ | ✅ | 1–50 MB | 汇报、社媒、无法运行 WebGL 的场合 |

> 「能跑」= 打开后场景可交互渲染，不是「能看到一张图」。

## MHTML 到底是什么

MHTML（RFC 2557）是 **MIME multipart 归档**：把 HTML 和它的资源塞进一个文件，每个资源一个 part，靠 `Content-Location` / `Content-ID` 互相引用。

它由浏览器「另存为 → 单个文件」生成，本质是**存档**，不是**应用格式**。

### 三个硬限制

1. **cid: 没有 base URL**
   `<script type="module">` 里的 `import './x.js'` 需要相对于文档 URL 解析。`cid:` 不是层级 URL，模块解析直接失败。
   → **任何用 importmap / ES Module 的场景，在 MHT 里都跑不起来。**

2. **浏览器支持碎片化**
   Chrome（Linux/部分平台）不打开 `.mht`；Safari 完全不支持；Firefox 需扩展；只有 Edge / IE 系原生支持。
   → 不能作为主交付格式。

3. **动态资源抓不到**
   运行时 `fetch`、`new Image()`、`TextureLoader` 加载的东西，保存时不存在，归档后必然缺失。

### 什么时候该用 MHT

- 需要作为**单个附件**发邮件 / 进 OA / 进知识库
- 内容以**静态图文**为主（报告、说明页、图文长页）
- 需要"留档可查"，不要求"打开能跑"

### 什么时候不该用

- 交付物是 WebGL / Canvas 交互场景 → 用 **standalone HTML**
- 需要二次编辑 → 用 **ZIP 工程包**
- 只需要模型 → 用 **GLB**

## 本 Skill 的产出路由

```
用户要什么？
├─ 打开就能玩/看                     → standalone HTML
├─ 发链接、体积越小越好               → CDN HTML
├─ 我要改素材、接着开发               → local HTML + 资源目录（forge_init --mode local）
├─ 单个文件留档/发邮件/OA            → MHT（export_mht.py）
├─ 打包带走全部源码                   → ZIP
├─ 只要 3D 模型                      → 页面内 GLTFExporter 导出 GLB
└─ 打印/汇报                          → PDF 图纸 或 MP4 录屏
```

## 命令

```bash
# 初始化三种运行模式之一
python3 scripts/forge_init.py ./out --mode standalone   # 默认，离线可跑
python3 scripts/forge_init.py ./out --mode cdn          # 最轻，需联网
python3 scripts/forge_init.py ./out --mode local        # HTML + ./three 资源目录

# 把已写好的 CDN 页面转成离线单文件
python3 scripts/build_standalone.py ./out/index.html -o ./out/index.html

# 封装成 MHTML 归档（静态资源自动 cid 重写）
python3 scripts/export_mht.py ./out/index.html -o ./out/scene.mht

# 静态验收
python3 scripts/validate_scene.py ./out/index.html
```

## 扩展其他形态的做法

**GLB**：页面里挂一个导出按钮，用户点一下得到模型。不要试图在服务端无头导出——没有 WebGL 上下文，几何和材质都构建不出来。

```js
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
new GLTFExporter().parse(subject, (buf) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([buf], { type: 'model/gltf-binary' }));
  a.download = 'model.glb';
  a.click();
}, (e) => console.error(e), { binary: true });
```

**PDF 图纸**：不要截 3D 视口（透视会失真）。用 `OrthographicCamera` 分别渲三视图，导出 PNG，再排版。尺寸标注必须来自几何参数，不能目测。

**MP4**：用 `canvas.captureStream()` + `MediaRecorder` 在页面内录，帧率锁 30，录制期间固定 `dt`，否则回放速度会漂。

## 一个反直觉的结论

**standalone HTML 比 MHT 更"单文件"。**

- standalone：1 个文件，内部零外部引用，任何浏览器双击可跑
- MHT：1 个文件，但内部是多个 part，多数浏览器不认，模块化 JS 还会失效

所以"想要一个文件"的诉求，正确答案是 standalone HTML，不是 MHT。
MHT 只在"必须塞进只认 MIME 归档的系统"时才有价值。
