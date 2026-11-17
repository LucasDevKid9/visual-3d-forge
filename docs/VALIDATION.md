# 验证记录

本文记录**实际跑出来的结果**，不是"应该能跑"。所有命令都在仓库根目录执行，
环境为 Linux + Python 3.11，three.js 0.187.0（`assets/vendor/`）。

---

## 一、测试套件

```bash
$ python3 -m pytest tests/ -q
26 passed in 0.87s
```

26 项分五层，每层都对应一条对外承诺：

| 层 | 用例数 | 断言的承诺 |
|---|---:|---|
| 文档完整性 | 9 | frontmatter 三字段、名称与目录一致、description 含触发词、索引↔文件双向一致、无占位符、无绝对路径 |
| 依赖完整性 | 3 | manifest 18 文件逐个重算 sha256、REVISION=187、importmap 指向本地 vendor |
| 工具行为 | 7 | 四脚本 `--help`、`bundle --self-test`、`vendor --self-test`、仅标准库、`api_lookup` 缺源码时给出可读错误 |
| 端到端 | 5 | D0/D2 校验 18 项、D2→D1 全链路、示例 strict 校验、反向测试（删 importmap） |
| 参数化 | — | 示例目录下每个 `.html` 都跑一遍 strict |

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
这一项正是 v2.0 白屏事故之后补的（见 `CHANGELOG.md` v2.0.1）。

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

这两条都符合 `docs/DESIGN-NOTES.md` 第 6 条的规律：**看起来对 ≠ 跑得起来 ≠ 结构正确**。
校验器能抓 API 幻觉与白屏，抓不到"零件插进另一个零件"——那要靠人眼看，或靠包围盒自检。
本仓库目前只能靠人眼，这是 `docs/ARCHITECTURE.md` 第八节承认的边界之一。

---

## 五、未验证的部分（不粉饰）

| 项 | 状态 | 原因 |
|---|---|---|
| `api_lookup.py` 完整链路 | **未验证** | 需要 three 源码（`npm pack three@0.187.0`），本包只含 build 产物；缺源码时脚本给可读错误并有测试覆盖该路径 |
| 真实浏览器多设备兼容 | 未验证 | 仅在 Chromium + SwiftShader 下渲染截图；Safari / 移动端未测 |
| 视觉质量 | 未量化 | 无参考图与渲染结果的像素比对 |
| `vendor.py` 重新裁剪 | 仅自检 | `--self-test` 校验目录结构；未对 npm 源码重跑 |
| D3（R3F）工程 | 未验证 | 只提供骨架，未执行 `npm i` / `vite build` |
