# 22 · 网页存档取件（Web Archive Intake）

> **与既有篇章的分工**：`14-offline-and-assets.md` 讲我们的产物怎么离线化；
> `15-output-formats.md` 讲交付形态怎么选；`scripts/export_mht.py` 是**导出**方向。
> 这一篇讲相反方向——**别人发来的存档怎么拆成参考素材**。两者不重叠。
>
> 这一篇解决一个具体场景：**别人发给你一个「就是这个质感」的网页，你手上却只有一个 `.mht` 文件**。
> 它讲三件事——这个格式到底是什么、为什么它不能当交付形态、以及怎么把它拆成能用的参考素材。

---

## 一、它是什么

MHTML（RFC 2557，扩展名 `.mht` / `.mhtml`）是**单文件网页存档**：

```
From: <Saved by Blink>                          ← Chrome 的「网页，单个文件」
Snapshot-Content-Location: https://…/           ← 存的是哪个页面
MIME-Version: 1.0
Content-Type: multipart/related; boundary="----MultipartBoundary--…----"

------MultipartBoundary--…----
Content-Type: image/svg+xml
Content-Transfer-Encoding: binary
Content-Location: https://…/assets/LOGO.svg

<SVG 的原始字节>
------MultipartBoundary--…----
…
```

三个结构性事实：

| 事实 | 含义 |
|---|---|
| `multipart/related` 容器 | 一个文件里装着 N 个分段，每个分段有独立的 `Content-Type` 与 `Content-Location` |
| `Content-Transfer-Encoding: binary` | **原始字节直存，不做 base64**。这是它相对 D1 的唯一技术优势 |
| 分段按 URL 互相引用 | 文档里的 `href`/`src` 指向原站 URL，浏览器靠 `Content-Location` 匹配回分段 |

实测一个 14 分段的样本（F*MMXX 网页快照，58 KB）：1 个 HTML + 8 个 SVG + 5 个 CSS，
全部 `binary` 编码。

---

## 二、为什么它不能当交付形态

这一条必须先钉死，否则会浪费一整天做出一个不会动的东西。

### 2.1 脚本在 .mht 里默认不执行

Chrome 从 `file://` 打开 `.mht` 时，把文档放进沙箱帧，`allow-scripts` 没开：

```
Blocked script execution in 'file:///…/e1-classic.mht' because the document's
frame is sandboxed and the 'allow-scripts' permission is not set.
```

实测四组对照（同一份 HTML，分别存成 `.html` 与 `.mht`）：

| 写法 | `.html` | `.mht` |
|---|---|---|
| `<script>` 经典脚本 | `CLASSIC_OK` | `BEFORE`（未执行） |
| `<script type="module">` 内联 | 执行 | `BEFORE` |
| `import './dep.js'`（依赖在另一分段） | 执行 | `BEFORE` |
| `@font-face` 从分段加载 | 执行 | 执行 |

也就是说：**样式和字体活下来，脚本全死。**

### 2.2 通过 HTTP 也不稳

以 `multipart/related` 正确 MIME 类型提供服务，Chrome 会当成下载而不是渲染；
以 `text/html` 提供则退化成纯文本。浏览器对 `.mht` 的支持是"存档查看器"级别，
不是"应用运行时"级别。

### 2.3 它天生缺件

存盘那一刻**还没加载完**的资源不会被收进容器。实测样本里：

- 线上原页有 `<script async type="module" src="bundle.js">`（2.0 MB）
- 存档里的 HTML **一个 `<script>` 都没有**（0 个），`<canvas>` 也是 0 个
- 字体（`.ttf`×3）、贴图（`.png`/`.jpg`）、模型（`.obj`/`.glb`）、HDR、音频全部缺失

所以你拿到的往往是一具**骨架**：DOM 在、CSS 在、SVG 在，动的那部分不在。

### 2.4 与 D0–D3 的定位对照

| | D1 单文件内嵌 | MHTML |
|---|---|---|
| 一个文件 | ✓ | ✓ |
| 断网可开 | ✓ | ✓（只能看） |
| **脚本可执行** | ✓ | ✗ |
| 体积开销 | base64 +33.3%（实测） | 0% |
| 适用 | **交付** | **存档 / 参考** |

> 结论：**MHTML 不是第五种交付形态**。它是"参考素材的容器"。
> 真想省那 33% 体积，代价是整个页面不再能动——对三维交付物来说等于归零。

---

## 三、它作为参考素材怎么用（G2 参考闸的第四个入口）

G2 参考闸原本只认图片与文字（R1–R5）。`.mht` 补上第五类：**可解构的活页面快照**。

```bash
python3 scripts/mht_unpack.py reference.mht --out ./ref-web
```

产出：

```
ref-web/
├── index.html        主文档，cid: 引用已改写成相对路径
├── _assets/…         其余分段按原 URL 路径还原（SVG / CSS / 字体…）
└── MANIFEST.json     分段清单 + 缺件推断 + 脚本/画布计数
```

脚本会直接告诉你这份快照缺什么，不用自己猜：

```
  主文档内 <script>：0 个　<canvas>：0 个
  缺件推断：脚本（.js）、字体（.ttf）、贴图（.png）
  ⚠ 主文档里没有任何脚本：这份快照不能执行，只能当参考素材读
```

### 拆完之后取什么

| 想拿走的东西 | 从哪取 | 喂给哪一阶段 |
|---|---|---|
| 配色与字距 | `_assets/inline-*.css` 里的 `:root` 变量与 `@font-face` | P2 材质假设表、P4 代码 |
| 品牌轮廓（logo / 图标 / 分隔线） | `_assets/**/*.svg` 的 `<path d="…">` | `09-part-library.md` 的轮廓类构造 |
| 构图与信息层级 | `index.html` 的 DOM 顺序与 `position` 规则 | `05-scene-systems.md` 的 HUD 布局 |
| 交互流程（选档 → 加载 → 开始） | DOM 里的 `#quality` / `#loading` / `#start` 三态 | P4 的加载状态机 |
| 它到底是什么技术做的 | `MANIFEST.json` 的缺件推断 | 判断「这是 WebGL 还是视频」 |

### 不能拿走的东西

- **渲染管线**。脚本不在容器里，你看不到它的后处理链。
  想要管线，去读它线上的 bundle，或者看 `04-algorithm-atlas.md`。
- **精确尺寸**。CSS 的 `em`/`vw` 是相对量；照抄会得到"看起来差不多但比例不对"的 HUD。
- **动画时序**。所有 `@keyframes` 都在，但驱动它们的 JS 不在。

---

## 四、源可信度：`.mht` 属于 R3

回到 `02-reference-deconstruction.md` 的分级：

| 等级 | 能得到什么 | 必须补什么 |
|---|---|---|
| **R3** | 外观、主轮廓、材质质感 | 深度、背面、尺度 |

`.mht` 快照落在 R3：你能看到**它长什么样**，看不到**它怎么算出来的**。
所以交付说明里必须写清：哪些是照着快照还原的，哪些是按引擎规则补的。
声称"1:1 复刻"就是精度谎言（红线第 1 条）。

---

## 五、检查表

- [ ] 确认这是存档而不是可运行页面：`<script>` 计数是否为 0
- [ ] 拆包后 `index.html` 能在浏览器里打开且样式正常
- [ ] `MANIFEST.json` 的缺件推断已读完，知道缺什么
- [ ] 只把 CSS / SVG / DOM 结构当参考，没有假装能拿到渲染管线
- [ ] 交付说明里标注了"参考等级 R3"
